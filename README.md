# RAGDocs AI

RAGDocs AI is a full-stack PDF assistant. Users upload PDFs and ask questions in plain English, and it answers from those documents and shows the file and page behind each answer.

**Further reading:**
- [workflow.md](workflow.md): how the system works, and what every folder, file and function does
- [interview.md](interview.md): interview preparation, from project pitch to deep RAG questions
- [followup.md](followup.md): follow-up questions and advanced RAG concepts, including MMR

## Try it with the demo account

On the login page, click **Log in with demo account**, or sign in manually:

| Email | Password |
|---|---|
| `user@email.com` | `User@1234` |

The backend creates this account when it starts. It's shared, so everyone using it sees the same documents and chats. Don't upload private files to it.

## Features

- Sign up and log in with JWT authentication and automatic login renewal
- PDF upload by drag and drop, with per-user storage
- Search across all documents, or only the ones you select
- Delete documents one at a time or all together
- Answers streamed live, with real progress steps and a Stop button
- Answers with file, page and excerpt sources
- Choice of models from Nebius, Google Gemini and OpenAI, plus an Auto mode with fallback
- Saved chat history, with recent messages used as memory
- Light and dark themes and a phone layout

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | React 18, Vite | Component-based UI with a fast dev server and build |
| Styling | Tailwind CSS, lucide-react | Consistent design without a heavy component library |
| Answers display | react-markdown, remark-gfm | Renders lists and tables safely |
| HTTP client | Axios | One shared client that attaches the login token |
| Backend | Flask | Small and explicit, which suits a focused API |
| Database layer | SQLAlchemy, PyMySQL | Same models work on MySQL and SQLite |
| Auth | Flask-JWT-Extended, Werkzeug | Stateless tokens and salted password hashes |
| PDF parsing | PyPDF2 | Simple page-by-page text extraction |
| Vector database | ChromaDB through langchain-chroma | Runs locally, persists to disk, supports metadata filters and MMR |
| Embeddings | Gemini `gemini-embedding-2` (3072 dimensions) | One consistent model for documents and questions |
| Answer models | Nebius, Gemini, OpenAI | Different providers, so one outage doesn't stop answers |
| Production server | gunicorn | Standard WSGI server |

## How it works

```text
Upload:  PDF -> extract text -> clean -> chunk -> embed -> store in Chroma
Ask:     question -> embed -> retrieve 6 chunks -> build prompt -> LLM -> streamed answer + sources
```

| Setting | Value |
|---|---|
| Chunk size | Up to 1050 characters, whole sentences, one page at a time |
| Overlap | 1 sentence |
| Retrieval | MMR (`k=6`, `fetch_k=18`, `lambda=0.65`), then similarity (`k=8`) as backup |
| Context sent to the model | Up to 6 chunks |
| Memory | Last 5 question and answer pairs |
| Temperature | 0.1 |
| Max output tokens | 1536 |
| Model thinking | Off for all models |
| Streaming | Server-Sent Events over `POST /api/chat/stream` |

### Available models

| Provider | Model | Role in Auto |
|---|---|---|
| Nebius Token Factory | `nvidia/Nemotron-3_5-Lightning` | Primary |
| Nebius Token Factory | `Qwen/Qwen3-235B-A22B-Instruct-2507` | Manual choice |
| Google Gemini | `GEMINI_MODEL` (default `gemini-2.5-flash`) | Secondary |
| OpenAI | `gpt-4.1` | Manual choice |

A model appears in the picker only if its provider's API key is set. A Gemini key is always required, because document search uses Gemini embeddings.

## Project structure

```text
backend/
  app.py               Entry point
  ragdocs_api/
    routes/            HTTP endpoints
    services/          PDF, vector, chat and LLM logic
    models.py          Database tables
    config.py          Settings from .env
  storage/             Uploaded PDFs and Chroma data (not in git)
frontend/
  src/
    components/        Auth, chat, sidebar and UI components
    hooks/             App state and theme
    api.js             Backend client
mysql_schema.sql       Manual MySQL schema
```

## Setup

You need Python 3.11, Node.js 22 and a Gemini API key. Nebius and OpenAI keys are optional. These commands use Windows syntax.

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

The API runs at `http://localhost:5000/api`.

Set these in `backend/.env`:

```env
JWT_SECRET_KEY=a-long-random-secret
GOOGLE_API_KEY=your-gemini-key
NEBIUS_API_KEY=your-nebius-key
OPENAI_API_KEY=your-openai-key
```

Never put real keys in `.env.example`, because git tracks that file.

### Database

The app uses the first of these that is set:

1. `DATABASE_URL`, such as `mysql+pymysql://user:password@host:3306/db`, or `sqlite:///C:/path/to/ragdocs.db` for an absolute SQLite path
2. `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD` and `MYSQL_DATABASE`
3. SQLite at `backend/ragdocs.db`

The app creates missing tables at startup. `python import_mysql_schema.py` is an optional way to do this manually, and `mysql_schema.sql` targets a database named `defaultdb`.

If a configured MySQL server is unreachable, the backend won't start. For local work, either bring the server back or set `DATABASE_URL` to a SQLite path.

Files in `backend/storage/` are organised by user id. Before switching to a different database, move those folders aside, or a new user with the same id could search an old user's documents.

### Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Open `http://localhost:5173`.

## API

All routes start with `/api`. Routes marked "Yes" need `Authorization: Bearer <token>`.

| Method | Route | Login | Purpose |
|---|---|---|---|
| GET | `/health` | No | Health check |
| POST | `/auth/register` | No | Create an account |
| POST | `/auth/login` | No | Get an access token (15 minutes) and a refresh token (30 days) |
| POST | `/auth/refresh` | Refresh token | Get a new access token |
| GET | `/config` | Yes | List available models and the Auto order |
| GET | `/documents` | Yes | List documents |
| POST | `/documents/upload` | Yes | Upload and index a PDF, up to 20 MB |
| DELETE | `/documents/<id>` | Yes | Delete one document, its file and its vectors |
| DELETE | `/documents` | Yes | Delete all of the user's documents |
| POST | `/chat/stream` | Yes | Ask a question and stream steps and tokens (used by the UI) |
| POST | `/chat` | Yes | Ask a question and get the full answer as JSON |
| GET | `/chat/history` | Yes | Last 20 messages |
| DELETE | `/chat/history` | Yes | Clear chat history |

Example request to `/chat` or `/chat/stream`:

```json
{ "question": "What was the budget?", "document_ids": [1, 2], "model": "auto" }
```

An empty `document_ids` list searches all of the user's documents.

## RAG scenarios: how this system behaves

These answers describe what the current code does, then what would improve it. More questions are in [interview.md](interview.md). Figures marked "estimate" are calculations, not load tests.

### What happens with 100 documents?

**Retrieval still returns only 6 chunks.** Assume 100 documents of 50 pages with about 2.5 chunks per page. That is about 12,500 chunks (estimate).

| Area | Current behaviour | Improvement |
|---|---|---|
| Search speed | Fine. Chroma uses an approximate index, so search doesn't scan every vector | None needed at this size |
| Relevance | Weakest area. Similar wording across documents competes for 6 places, and only 18 candidates enter MMR | Retrieve about 50 candidates, then rerank down to 6 |
| Exact terms | Vector search can miss codes, names and IDs | Add BM25 keyword search and merge results |
| Coverage | One document can take all 6 places | Limit chunks per document |
| "Summarise everything" | 6 chunks can't represent 100 documents | Store document summaries and use map-reduce |
| Question latency | One `store.get` per document on every question | Track index status in SQL |
| Indexing time | 12,500 calls at a measured 0.64 s is about 2.2 hours in series (estimate) | Batch embeddings and use background jobs |
| Storage | 3072 dimensions at 4 bytes each is about 150 MB of raw vectors (estimate) | Fine at this size |

### How would you know retrieval got worse?

Build a test set of questions with known correct passages, then track recall@k, MRR and nDCG before and after each change. Measure faithfulness and answer relevance separately, so a retrieval failure isn't confused with a generation failure. This project has no automated evaluation yet.

### What if the answer isn't in the documents?

Retrieval still returns 6 chunks, because no relevance threshold exists. The prompt tells the model to answer only from the context and to say what is uncertain. A safer design rejects weak matches before calling the model, with a threshold tuned on test data.

### What if a user asks a follow-up like "what about its budget?"

The model sees recent chat, but retrieval searches the raw question, so the search may miss the right passage. The fix is to rewrite the question into a standalone one before embedding it.

### What if the PDF is scanned?

PyPDF2 finds no text, so the upload is rejected with "No readable text was found". The fix is an OCR step, used only on pages without text.

### What if the answer spans two pages?

Chunks never cross page boundaries, which keeps citations exact but can separate related text. The fix is to allow overlap across pages and store a page range, or to fetch neighbouring chunks after retrieval.

### What if the embedding model changes?

The collection name includes the model name, so old vectors are never mixed with new ones. Each document is re-embedded the next time a question includes it. Vectors from different models aren't comparable, so this separation is required.

### What if the primary LLM fails?

In Auto mode, an error or empty reply before the first token moves to the secondary model. A failure after text has appeared shows an error instead, because streamed text can't be taken back. A model chosen manually has no fallback. Gemini is still a single point of failure for retrieval, because embeddings depend on it.

### Can a PDF attack the system?

Yes. Text inside a PDF can include instructions aimed at the model, known as indirect prompt injection. Only that user's own documents reach the prompt, and the model has no tools to misuse, which limits the damage. It could still distort an answer. Mitigations include clearly separating data from instructions and checking output.

## Known limitations

Key gaps are slow synchronous indexing, no OCR, no reranking or keyword search, and no relevance threshold. The full list is in [workflow.md](workflow.md#6-known-limitations).
