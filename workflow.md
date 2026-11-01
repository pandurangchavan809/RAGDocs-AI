# RAGDocs AI: System Workflow and Code Guide

This document explains how the system works today, why each folder and file exists, and what each function does. Everything here describes the current code. Planned improvements are in [interview.md](interview.md).

## 1. What the system does

A user signs in, uploads PDFs and asks questions in plain English. The backend finds the most relevant passages in that user's PDFs, sends them to a language model with strict instructions, and returns an answer with the file and page each passage came from.

```text
Browser (React, port 5173)
   |  HTTPS + JSON, JWT in the Authorization header
   v
Flask API (routes -> services)
   |-- SQL database     users, document records, chat history
   |-- Disk             original PDFs
   |-- ChromaDB         chunk text, metadata and embeddings, one store per user
   |-- Gemini API       embeddings, and answers when Gemini is selected
   |-- Nebius API       answers (Nemotron, Qwen)
   `-- OpenAI API       answers (gpt-4.1)
```

Why there are three kinds of storage:

| Store | Holds | Why this store |
|---|---|---|
| SQL (MySQL, or SQLite locally) | Users, document records, chats | Relational data, unique constraints, simple queries by user |
| Disk (`storage/uploads/`) | Original PDF files | Files don't belong in SQL, and they allow re-indexing later |
| Chroma (`storage/chroma/`) | Chunks and vectors | Built for nearest-neighbour search and metadata filters |

## 2. The four main flows

### 2.1 Register and log in

1. `AuthPage.jsx` collects the form, and `handleAuthSubmit` in `useRagDocsApp.js` posts it.
2. `POST /api/auth/register` lowercases the email, rejects duplicates with 409, and stores a salted hash from `generate_password_hash`.
3. `POST /api/auth/login` checks the hash and returns two signed JWTs whose identity is the user id: an access token (15 minutes) and a refresh token (30 days).
4. The frontend saves both tokens and the user in `localStorage`, and `setAuthToken` adds `Authorization: Bearer <access token>` to every Axios request.
5. Protected routes use `@jwt_required()` and read the user id from the token, never from the request body. A user can't ask for another user's data by changing a parameter.

**Demo account:** at startup, `ensure_demo_user` creates `user@email.com` if it doesn't exist, and never changes an existing account. The login page has a button that logs in with these credentials directly. It uses the normal login route, with no special access.

**Automatic renewal:**

1. A request returns 401 because the access token has expired.
2. `refreshAccessToken` in `api.js` sends the refresh token to `POST /api/auth/refresh`, which returns a new access token.
3. The original request is retried once with the new token, and the user sees nothing.
4. If the refresh token has also expired, the user returns to the login page with a "session expired" message.

Renewal adds no cost to normal requests. It runs only after a 401, about once every 15 minutes of use, and requests that fail together share one refresh call. An answer already streaming is unaffected, because the token is checked only when the stream starts.

### 2.2 Upload a PDF (ingestion)

```text
UploadDialog -> POST /api/documents/upload
  1. Validate       file present, name ends in .pdf, size <= 20 MB
  2. Save           storage/uploads/<user_id>/<uuid>.pdf
  3. Extract        PyPDF2 reads each page's text
  4. Clean          normalize_pdf_text removes noise and short fragments
  5. Chunk          split_text builds sentence-based chunks, max 1050 chars
  6. Record         a row is written to the documents table
  7. Embed + store  each chunk gets a Gemini vector, stored in the user's Chroma store
```

- **Unique stored names:** the UUID stops two uploads with the same name from overwriting each other, and stops user-supplied names from reaching the file path.
- **Order matters:** the SQL row is committed before embedding. If embedding fails, the request errors but the row remains. The next question then finds the document has no vectors and re-indexes it through `ensure_documents_indexed`.
- **It is synchronous:** the request stays open until every chunk is embedded. I measured about 0.64 s per embedding call, so a 125-chunk PDF takes about 80 seconds.

### 2.3 Ask a question (the RAG flow)

```text
Composer -> POST /api/chat/stream { question, document_ids, model }

routes/chat.py
  - Validate the question and model
  - Check that every document id belongs to this user
  - Open a Server-Sent Events (SSE) response

services/chat_service.stream_question
  1. ensure_documents_indexed   re-index anything missing or from an old version
  2. Embed the question         step event: "Embedding query"
  3. retrieve_relevant_chunks   step event: "Retrieving context"
       a. MMR search            k=6, fetch_k=18, lambda=0.65
       b. Similarity search     k=8
       c. Remove duplicates     by (document_id, chunk_index)
       d. Quality filter        drop low-signal chunks if any good ones remain
       e. Keep the first 6
  4. Build the prompt           rules + last 5 Q&A pairs + chunks + question
  5. llm_service.stream_answer  step event: "Sending to <model>", ends at first token
       Auto:    primary, then secondary if it fails before its first token
       Chosen:  that model only, with no fallback
  6. Token events               answer text as it arrives

routes/chat.py
  - Save the question, answer, document ids and sources to SQL
  - Send the done event with message_id and total_ms
```

The browser receives these events:

| Event | Contains | UI effect |
|---|---|---|
| `step` | `id`, `label`, `status`, `duration_ms`, `detail` | Updates the live step card |
| `sources` | File, page and excerpt list | Shown once the answer finishes |
| `model` | Model that really answered | Shown under the answer |
| `token` | A piece of answer text | Appended to the answer |
| `done` | `message_id`, `total_ms` | Answer moves into history |
| `error` | Message | Red banner, and the question returns to the input |

Details worth knowing:

- **Thinking is off for every model.** Nebius gets `enable_thinking: false`, Gemini gets `thinking_budget=0`, and `gpt-4.1` has no thinking mode.
- **Streaming uses `fetch`, not `EventSource`.** `EventSource` can't send POST bodies or an `Authorization` header.
- **Fallback happens only before the first token.** Text already shown can't be taken back, so a failure mid-answer shows an error and nothing is saved.
- **Stop is real but local.** Pressing Stop closes the connection, the backend stops, and nothing is saved. The partial answer stays on screen until reload.
- **Gemini is released word by word.** Its API sends large blocks, so the backend splits each block into words with a 12 ms gap. The text is real, but this pacing is added by us.
- **Step details aren't stored.** Reloaded answers don't show the step card.
- **The query is embedded once.** Both searches reuse the same vector.
- **MMR results come first.** MMR usually returns 6 chunks and the list is cut to 6, so similarity results mostly matter when MMR fails or returns fewer. It works as a fallback, not a true merge.
- **No relevance threshold exists.** Similarity scores are thrown away, so an off-topic question still retrieves 6 chunks. Only the prompt's "answer only from the context" rule stops a made-up answer. The "could not find matching content" message appears only when nothing at all is retrieved.
- **Retrieval ignores chat history.** Only the raw question is embedded. A follow-up such as "what about its budget?" is searched as written, even though the model sees the earlier messages.
- **Sources mean "retrieved", not "used".** All retrieved chunks are returned as sources, whether or not the model relied on them.

### 2.4 Choose a model

1. After login, the frontend calls `GET /api/config`.
2. `get_available_models` returns only models whose provider has an API key, so the picker can't offer a model that can't run.
3. The picker saves the choice in `localStorage` and resets to Auto if the server stops offering that model.
4. `POST /api/chat` rejects any model id that isn't available.
5. The response names the model that really answered, and the UI shows it under new answers. The model isn't stored in SQL, so reloaded answers don't show it.

## 3. Folder and file guide

```text
RAGDocs AI/
|-- README.md             Overview, setup, RAG scenarios
|-- workflow.md           This file
|-- interview.md          Interview preparation
|-- reference.md          UI design brief taken from DataPilot
|-- mysql_schema.sql      Manual MySQL table definitions
|-- backend/              Flask API and the RAG pipeline
`-- frontend/             React user interface
```

### 3.1 Backend root: `backend/`

| File | Why it exists |
|---|---|
| `app.py` | Entry point. Calls `create_app()` so that `flask` and gunicorn have an `app` object. Running it directly starts the debug server on port 5000. It holds no business logic. |
| `requirements.txt` | Python dependencies. Versions aren't pinned, so a fresh install can pull different versions. |
| `.env` | Real secrets and settings. Ignored by git. |
| `.env.example` | Safe template listing every variable. Tracked by git, so it must never contain real keys. |
| `Procfile` | Production start command for platforms such as Render or Heroku: gunicorn with a 120-second timeout. |
| `import_mysql_schema.py` | Optional script that runs `mysql_schema.sql` against MySQL. The app also creates missing tables itself at startup. |
| `documind.db` | Old SQLite file from an earlier project name. Nothing in the code uses it, so it can be removed. |
| `storage/` | Runtime data: `uploads/` for PDFs and `chroma/` for vectors. Ignored by git. |
| `.venv/` | The project's own Python environment. Ignored by git. |

### 3.2 App package: `backend/ragdocs_api/`

The package separates HTTP handling (`routes/`) from the logic (`services/`). Routes validate input and shape responses, and services do the work, so RAG logic can change without touching HTTP code.

| File | What it provides |
|---|---|
| `__init__.py` | `create_app()`, the application factory. Loads config, enables CORS, starts the database and JWT, registers error handlers and routes, and creates missing tables. A factory lets tests and servers build the app with different settings. |
| `config.py` | Loads `.env`, creates storage folders, and defines `INDEX_VERSION`. Key functions: `get_cors_origins` (allowed frontend origins), `build_database_uri` (`DATABASE_URL`, then `MYSQL_*`, then SQLite), `build_engine_options` (connection health checks, recycling and SSL). |
| `extensions.py` | Creates the shared `db` and `jwt` objects. A separate file avoids circular imports between models and the app. |
| `models.py` | Database tables: `User`, `Document`, `ChatMessage`. `document_ids` and `sources` are stored as JSON text. |
| `errors.py` | Turns database connection failures into a clean 503 response instead of a stack trace. |

### 3.3 Routes: `backend/ragdocs_api/routes/`

| File | Endpoints |
|---|---|
| `__init__.py` | `register_blueprints` mounts every route group under `/api`. |
| `auth.py` | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh` |
| `documents.py` | `GET /documents`, `POST /documents/upload`, `DELETE /documents/<id>`, `DELETE /documents` (all) |
| `chat.py` | `GET /health`, `GET /config`, `GET /chat/history` (last 20), `DELETE /chat/history`, `POST /chat/stream` (used by the UI), `POST /chat` (same pipeline, full JSON reply) |

### 3.4 Services: `backend/ragdocs_api/services/`

**`pdf_service.py`: turns a PDF into clean chunks**

| Function | What it does |
|---|---|
| `allowed_file` | Accepts names ending in `.pdf`. This checks the name only, not the file's contents. |
| `extract_pdf_pages` | Reads each page and keeps its page number, which later powers citations. |
| `normalize_pdf_text` | Removes null characters and extra spaces, rebuilds paragraphs from broken lines, and drops paragraphs under 10 words. |
| `is_meaningful_text` | Requires at least `min_words` words (default 18) and at least 45% letters. Rejects page numbers, tables of figures and other noise. |
| `split_sentences` | Splits on `.`, `!` or `?` followed by whitespace. |
| `split_text` | Builds chunks of up to 1050 characters from whole sentences, one page at a time, repeating the last sentence as overlap. |

**`vector_store_service.py`: the link to Chroma**

| Item | What it does |
|---|---|
| `GeminiEmbeddings` | Adapts Gemini to LangChain's `Embeddings` interface. Adds different prefixes to documents and queries. |
| `get_embedding_model` | Returns one cached embedding object. |
| `get_embedding_collection_name` | Puts the embedding model and index version in the collection name, so vectors from different models are never mixed. |
| `get_vector_store` | Opens the Chroma store at `storage/chroma/user_<id>`, which is what separates users' vectors. |

**`document_service.py`: keeps SQL and Chroma in step**

| Function | What it does |
|---|---|
| `get_user_documents` | Fetches a user's documents, optionally limited to given ids. |
| `delete_document_chunks` | Removes a document's vectors, before re-indexing or deleting it. |
| `delete_user_documents` | Deletes each document's vectors, then its file, then its SQL row. A failure leaves it listed for a retry, with no searchable leftovers. |
| `store_document_chunks` | Writes chunks with stable ids (`doc-<id>-chunk-<n>`) and metadata: user, document, file name, chunk number, page and index version. |
| `document_needs_reindex` | True if a document has no vectors or was indexed with an older `INDEX_VERSION`. |
| `ensure_documents_indexed` | Repairs or upgrades documents when a question arrives. Changing the embedding model or `INDEX_VERSION` therefore re-indexes lazily, with no migration script. |

**`chat_service.py`: the RAG pipeline**

| Function | What it does |
|---|---|
| `get_recent_memory` | Loads the user's last 5 question and answer pairs. |
| `retrieve_relevant_chunks` | Runs the retrieval steps from section 2.3. |
| `build_source_payload` | Removes duplicates and creates the source data shown in the UI. |
| `build_prompt` | Combines the rules, memory, chunks and question. |
| `step_event` | Creates a step event with its status and real duration. |
| `stream_question` | Runs the whole pipeline, yielding each stage and token as it happens. |
| `answer_question` | Collects `stream_question` into one complete answer for `POST /chat`. |

**`demo_service.py`: public demo account**

`ensure_demo_user` creates the demo account once. If two server workers start together, the unique email rule stops a duplicate, and the second worker carries on.

**`gemini_service.py`: Gemini setup**

Reads the Gemini settings once, finds the key from `GEMINI_API_KEY` or `GOOGLE_API_KEY`, and builds a cached client. Temperature and max tokens defined here are shared with all providers. The thinking budget is fixed at 0.

**`llm_service.py`: the multi-provider layer**

| Function | What it does |
|---|---|
| `get_declared_models` | Lists every configured model in display order. |
| `get_role_ids` | Finds the primary and secondary models. Defaults are the first Nebius model and `GEMINI_MODEL`. |
| `get_available_models` | Returns only models with an API key, in the shape the picker needs. |
| `get_auto_chain` | Returns the order Auto will try. |
| `is_selectable_model` | Validates the model id sent by the client. |
| `get_model_label` | Turns a model id into a short display name. |
| `stream_with_gemini` | Streams from Gemini through its own SDK and releases text word by word. |
| `stream_with_openai_compatible` | Streams from Nebius or OpenAI through the OpenAI SDK, and turns thinking off for Nebius. |
| `stream_with_model` | Picks the provider. |
| `stream_answer` | Runs the fallback loop, and treats an empty reply as a failure. |

Nebius and OpenAI share one function because Nebius offers an OpenAI-compatible API, so only the base URL and key differ. The request timeout is 45 seconds with no SDK retries, so Auto reaches its fallback quickly.

### 3.5 Utilities: `backend/ragdocs_api/utils/`

`responses.py` provides `error_response`, which gives every handled error the same shape: `{"error": "message"}`.

### 3.6 Frontend root: `frontend/`

| File | Why it exists |
|---|---|
| `index.html` | Page shell. Loads fonts and sets the theme before first paint, which prevents a white flash in dark mode. |
| `package.json` | Dependencies and the `dev`, `build` and `preview` scripts. |
| `vite.config.js` | Enables React in Vite. |
| `tailwind.config.js` | Brand colours, fonts, animations and class-based dark mode. |
| `postcss.config.js` | Runs Tailwind and Autoprefixer during the build. |
| `.env.example` | Template for `VITE_API_URL`. Vite exposes `VITE_` variables to the browser, so secrets must never go in them. |
| `public/favicon.svg` | Browser tab icon. |

### 3.7 Frontend source: `frontend/src/`

| File | What it does |
|---|---|
| `main.jsx` | Starts React and loads the CSS. |
| `App.jsx` | Shows the login page or the workspace, and controls the sidebar and upload dialog. |
| `api.js` | Shared Axios client, `setAuthToken`, automatic token renewal, and `streamChat`, which reads the SSE response. |
| `index.css` | Base styles, gradient and shimmer effects, and Markdown answer styling. |
| `constants/app.js` | Default form values and `localStorage` key names. |
| `utils/cn.js` | Joins CSS class names. |
| `utils/formatTime.js` | Formats timestamps. |
| `hooks/useRagDocsApp.js` | Holds all app state and API calls: session, documents, history, model, upload, questions and errors. Components stay focused on display. |
| `hooks/useTheme.js` | Switches and saves light or dark mode. |

**Components**

| File | What it shows |
|---|---|
| `auth/AuthPage.jsx` | Log in and sign up forms. |
| `sidebar/Sidebar.jsx` | Clear chat, user row, documents card, document checkboxes, saved questions, theme switch. Becomes a drawer on phones. |
| `sidebar/UploadDialog.jsx` | Drag-and-drop or file-picker upload. |
| `chat/ChatView.jsx` | Header, message list, follow-the-latest scrolling, errors and composer. |
| `chat/ModelPicker.jsx` | Grouped model menu. Becomes a plain label when only one model is available. |
| `chat/EmptyState.jsx` | Welcome screen, suggestion cards and upload prompt. |
| `chat/Messages.jsx` | User bubble and assistant answer, live or finished. |
| `chat/StepTrace.jsx` | Live step card with real timings, collapsing to "Completed in X s" afterwards. |
| `chat/Markdown.jsx` | Renders answers as Markdown. Raw HTML in an answer isn't executed. |
| `chat/SourcesBlock.jsx` | Collapsible list of file, page and excerpt. |
| `chat/Composer.jsx` | Auto-growing input, the model picker, and a send button that becomes Stop while answering. Disabled until a document exists. |
| `shared/NoticeBanner.jsx` | Short success messages. |
| `ui/Button.jsx`, `ui/Dialog.jsx`, `ui/Logo.jsx` | Reusable building blocks. |

## 4. Database tables

| Table | Key columns | Purpose |
|---|---|---|
| `users` | `id`, `name`, `email` (unique), `password_hash`, `created_at` | Accounts |
| `documents` | `id`, `user_id`, `original_name`, `stored_name`, `chunk_count`, `created_at` | Links a user to a stored PDF |
| `chat_messages` | `id`, `user_id`, `question`, `answer`, `document_ids`, `sources`, `created_at` | History, UI display and prompt memory |

One row holds one full question and answer. There is no conversation table, so each user effectively has a single continuous chat.

## 5. Configuration

| Variable | Purpose |
|---|---|
| `DATABASE_URL` or `MYSQL_*` | Database connection. SQLite is used if neither is set. |
| `MYSQL_SSL_MODE`, `DB_POOL_*` | MySQL SSL and connection pool behaviour. |
| `JWT_SECRET_KEY` | Signs login tokens. |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | **Required**, even when another model answers, because embeddings use Gemini. |
| `GEMINI_MODEL`, `GEMINI_TEMPERATURE`, `GEMINI_MAX_OUTPUT_TOKENS` | Generation settings. Temperature and max tokens apply to all providers. |
| `EMBEDDING_MODEL` | Embedding model. Changing it re-embeds every document on its next use. |
| `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, `NEBIUS_MODELS` | Nebius access and comma-separated model list. |
| `OPENAI_API_KEY`, `OPENAI_MODELS` | OpenAI access and model list. |
| `LLM_PRIMARY_MODEL`, `LLM_SECONDARY_MODEL` | Override Auto's order, as `provider:model`. |
| `FRONTEND_URL` or `FRONTEND_URLS` | Allowed browser origins for CORS. |
| `VITE_API_URL` | Frontend setting for the backend address. |

## 6. Known limitations

| Limitation | Effect |
|---|---|
| The demo account is public and shared, with no rate limits | Visitors see each other's uploads and chats, anyone can clear its history, and heavy use spends real API credit |
| Refresh tokens can't be revoked on the server | Logout clears them from the browser, but a stolen refresh token works until it expires after 30 days |
| Vector and upload folders are named by user id | Switching to a different database can make a new user share an old user's folder, so these folders must be cleared or moved when the database changes |
| Files live on one machine | Documents uploaded elsewhere are listed but can't be searched here, because their PDFs and vectors aren't on this disk |
| Gemini is required for all retrieval | If Gemini is down, questions fail even when other models are healthy |
| Uploads are synchronous, with one embedding call per chunk | Large PDFs are slow and can hit the 120-second production timeout |
| `Procfile` runs one gunicorn sync worker | One long request or streaming answer blocks every other user |
| Every question checks every in-scope document | Question latency grows with the number of documents |
| No OCR | Scanned PDFs are rejected because they contain no readable text |
| Short paragraphs under 10 words are dropped | Tables, short lists and headings can be lost |
| Deleting a document keeps chat history | Old answers stay visible, and recent ones can still reach the model as memory until the chat is cleared |
| No reranker, keyword search or relevance threshold | See the improvement plan in [interview.md](interview.md) |
| Chroma and uploads are on local disk | Platforms with temporary disks lose them, and several servers can't share them |
