# RAGDocs AI Interview Guide

## 1. One-line project intro

RAGDocs AI is a full-stack RAG-based PDF assistant where users upload PDFs, the backend chunks and embeds the text, stores embeddings in Chroma, retrieves the most relevant chunks for a question, and uses Gemini to generate grounded answers with source excerpts.

## 2. 30-second interviewer explanation

I built a PDF question-answering system using React on the frontend and Flask on the backend. Users can register, upload PDFs, and ask questions across one document or multiple documents. On the backend, I extract PDF text, clean it, split it into chunks, generate Gemini embeddings, store them in ChromaDB, retrieve relevant chunks using MMR plus similarity search, and then send the retrieved context to Gemini with a low temperature so answers stay factual and consistent.

## 3. 60-90 second detailed explanation

The project is a user-specific RAG pipeline, not just a generic chatbot.

1. A user logs in with JWT authentication.
2. The user uploads a PDF.
3. The backend extracts readable text from each page using `PyPDF2`.
4. The text is normalized and split into meaningful chunks.
5. Each chunk is embedded with Gemini embedding model `gemini-embedding-2`.
6. Embeddings are stored in a user-specific Chroma vector store.
7. When the user asks a question, the app retrieves relevant chunks using MMR search and similarity search.
8. Those chunks, along with recent chat memory, are inserted into a zero-shot prompt.
9. Gemini `gemini-2.5-flash` generates the answer.
10. The answer and source excerpts are saved in the SQL database and shown in the UI.

## 4. Architecture in simple words

- Frontend: React + Vite + Tailwind + Axios
- Backend: Flask + SQLAlchemy + Flask-JWT-Extended
- LLM: Google Gemini via the official `google-genai` SDK
- Vector DB: ChromaDB
- Embeddings: Gemini embeddings
- PDF parsing: `PyPDF2`
- Database: SQLite by default, MySQL supported through environment config

## 5. Exact LLM, RAG, and LangChain-related parameters used in this project

### LLM generation parameters

| Parameter | Value in project | Why it is used |
|---|---:|---|
| `GEMINI_MODEL` | `gemini-2.5-flash` | Fast generation model for chatbot responses |
| `GEMINI_TEMPERATURE` | `0.1` | Low randomness for factual RAG answers |
| `GEMINI_MAX_OUTPUT_TOKENS` | `1536` | Keeps answers detailed but bounded |
| `GEMINI_THINKING_BUDGET` | `256` | Enables a moderate reasoning budget in Gemini 2.5 |
| `response_mime_type` | `text/plain` | Forces plain-text output |

### Embedding and vector parameters

| Parameter | Value in project | Why it is used |
|---|---:|---|
| `EMBEDDING_MODEL` | `gemini-embedding-2` | Creates vector embeddings for chunks and queries |
| Embedding style for documents | `title: pdf chunk | text: {text}` | Adds a small task hint for chunk embeddings |
| Embedding style for queries | `task: question answering | query: {text}` | Helps align query embeddings to retrieval use case |
| Vector store | Chroma | Stores and searches embeddings |
| Collection naming | `documents_{embedding_model}_{index_version}` | Keeps index versions separated |
| Index version | `ragdocs_v2` | Supports re-indexing when chunking or metadata changes |

### Retrieval parameters

| Parameter | Value in project | Why it is used |
|---|---:|---|
| MMR `k` | `6` | Final diverse chunks from MMR retrieval |
| MMR `fetch_k` | `18` | Candidate pool before diversity selection |
| MMR `lambda_mult` | `0.65` | Balances similarity and diversity |
| Similarity search `k` | `8` | Backup retrieval to catch additional relevant chunks |
| Final returned chunks | up to `6` | Keeps prompt context compact |
| Document filter | selected `document_ids` or all docs | Supports focused or cross-document querying |
| Deduplication key | `document_id + chunk_index` | Prevents duplicate chunks in context |

### Chunking and PDF preprocessing parameters

| Parameter | Value in project | Why it is used |
|---|---:|---|
| `max_chunk_chars` | `1050` | Keeps chunks small enough for retrieval and prompt context |
| `overlap_sentences` | `1` | Preserves continuity between neighboring chunks |
| Paragraph cleaning threshold | `min_words=10` in one preprocessing stage | Removes tiny noisy paragraphs |
| Meaningful chunk threshold | `min_words=18` | Filters low-signal text before indexing and answer generation |
| Letter ratio threshold | `0.45` | Rejects noisy text with too many non-letter characters |
| Sentence split rule | regex on `.`, `!`, `?` | Makes chunking more natural than fixed-length splitting |

### Memory and chat parameters

| Parameter | Value in project | Why it is used |
|---|---:|---|
| Recent memory used in prompt | last `5` messages | Gives short conversational continuity |
| Chat history API response | last `20` messages | Keeps UI history manageable |
| Sources per answer | based on unique retrieved chunks | Shows explainability in the UI |

### App and deployment-related parameters

| Parameter | Value in project | Why it is used |
|---|---:|---|
| Max upload size | `20 MB` | Basic upload safety |
| `FRONTEND_URL` | `http://localhost:5173` by default | CORS control |
| `DB_POOL_RECYCLE_SECONDS` | `240` | MySQL connection stability |
| `DB_POOL_TIMEOUT_SECONDS` | `30` | MySQL connection timeout |
| Frontend API URL | `http://localhost:5000/api` | Frontend-backend communication |

## 6. What role LangChain actually plays here

This is an important interview point: the project does not use a full LangChain chain like `RetrievalQA` or an agent.

LangChain is used mainly for:

- `langchain-chroma` to integrate with Chroma
- the `Embeddings` interface so a custom Gemini embedding class can plug into Chroma cleanly

Strong answer:

> I used LangChain as a light integration layer, mainly for the Chroma vector store and embeddings interface. The retrieval and prompting logic are custom Python functions, so I kept the pipeline transparent and easy to explain.

## 7. Prompting style used in this project

This project uses zero-shot prompting.

Why it is zero-shot:

- The prompt gives instructions only
- There are no example question-answer pairs
- There is no few-shot prompt template
- The retrieved chunks are inserted directly as context

Core prompt behavior in the project:

- answer only from the provided PDF context
- write one clear answer in plain English
- ignore broken fragments and repeated template text
- if asked about the whole document, first summarize in 2-4 sentences, then add key points
- if context is incomplete, say what is clear and what is uncertain
- do not invent unsupported details

Strong answer:

> The chatbot uses zero-shot prompting with retrieved context. I did not use few-shot examples because the task is document-grounded QA, and a direct instruction prompt is simpler, cheaper, and easier to control.

## 8. Best answer for the temperature interview question

If they ask:

> What temperature do you use for a RAG chatbot?

Say:

> In this project I used `temperature=0.1` because it is a RAG-based PDF assistant. For RAG systems I usually keep temperature between `0.0` and `0.3` so the model stays factual and consistent with the retrieved documents.

Easy memory trick:

- `0.0` -> highly deterministic, fact-focused
- `0.1 to 0.3` -> best for RAG and QA systems
- `0.7` -> more natural conversation
- `1.0+` -> more creative generation

Short version:

> I typically use around `0.1` or `0.2` for RAG, and higher values only for creative or open-ended tasks.

## 9. How to explain your retrieval strategy

Strong answer:

> I used a two-step retrieval style. First, I try Max Marginal Relevance search to get relevant but non-redundant chunks. Then I also run similarity search as a backup. After that I deduplicate chunks and keep the best six for the final prompt. This improves diversity while still staying relevant.

Why MMR matters:

- pure similarity search can return many nearly identical chunks
- MMR improves coverage of different parts of the document
- this is especially useful when multiple chunks contain similar wording

## 10. How to explain memory

Strong answer:

> I store chat history in SQL and inject only the latest five messages into the prompt. That gives some conversational continuity without making the prompt too large or expensive.

Be honest:

- this is short-term chat memory, not long-term semantic memory
- it is useful for follow-up questions
- it is not a separate memory retrieval system

## 11. How to explain multi-document querying

Strong answer:

> The app supports both focused and broad retrieval. If the user selects specific PDFs, retrieval is filtered to those document IDs. If nothing is selected, the system searches across all uploaded PDFs for that user.

Why this is a good feature:

- supports comparison questions across documents
- gives users control over retrieval scope
- keeps results user-specific and secure

## 12. Security and backend design points you can mention

- JWT authentication protects the API
- selected document IDs are validated against the logged-in user
- PDFs and vector stores are separated per user
- filenames are sanitized with `secure_filename`
- upload type is restricted to PDF
- upload size is limited to 20 MB
- answers and sources are persisted for chat history

Strong answer:

> I made the RAG flow user-specific. Each user has isolated uploaded files, isolated vector storage, and document ownership checks before retrieval.

## 13. Honest limitations of the current project

You should say these confidently. Interviewers usually like honest engineering judgment.

- It depends on text-based PDFs. Scanned PDFs without OCR will not work well.
- There is no reranker model after retrieval.
- There is no hybrid retrieval using both keyword and vector search.
- There is no streaming response in the UI.
- Embeddings are generated per text item and could be optimized with batching.
- There is no document deletion flow in the current UI/backend.
- Memory is limited to the recent chat window, not a semantic memory layer.
- The prompt is strong but still hand-written, not evaluated with formal benchmarks.

Strong answer:

> The current version is strong as a learning-oriented production-style prototype, but I would still improve OCR support, retrieval quality, document lifecycle management, and observability before calling it fully production-ready.

## 14. Improvements you can propose if they ask "what next?"

- add OCR for scanned PDFs
- add reranking after vector retrieval
- add hybrid search with BM25 plus vector search
- support streaming answers
- batch embeddings to improve indexing performance
- add document delete and re-upload management
- add citation highlighting tied to exact PDF pages
- add background jobs for indexing large PDFs
- add prompt evaluation and retrieval quality metrics
- move from SQLite to managed MySQL or Postgres in production

## 15. Interview questions they may ask about this exact project

### 1. What problem does your project solve?

Answer:

> It helps users ask natural-language questions over their PDF documents instead of manually reading everything. The system retrieves relevant sections from uploaded PDFs and generates grounded answers with source excerpts.

### 2. Why is this a RAG system and not just a chatbot?

Answer:

> Because the answer is grounded in retrieved document chunks. The model does not rely only on pretrained knowledge. It first retrieves relevant context from the user's PDFs and then answers from that context.

### 3. Why did you choose low temperature?

Answer:

> Because this is a document QA use case. I want consistent and factual answers, so I used `0.1` instead of a creative setting.

### 4. Why did you choose chunking?

Answer:

> Full PDFs are too large and noisy to send directly to the model. Chunking improves retrieval precision, reduces prompt size, and lets the vector database search at a more meaningful granularity.

### 5. Why did you use sentence overlap?

Answer:

> A small overlap preserves context between chunks so we do not lose meaning at chunk boundaries.

### 6. Why use MMR instead of only similarity search?

Answer:

> MMR helps avoid redundant chunks and gives better coverage across the document, especially when many chunks look similar.

### 7. Why did you not use a LangChain RetrievalQA chain?

Answer:

> I wanted the RAG flow to be explicit and interview-friendly. Writing custom retrieval and prompting logic made it easier to control, debug, and explain each step.

### 8. How is chat memory handled?

Answer:

> I save the conversation in the database and only pass the most recent five turns into the prompt to keep follow-up questions coherent without growing token usage too much.

### 9. How do you prevent hallucination?

Answer:

> I use retrieval grounding, a low temperature, a prompt that explicitly says answer only from context, and source excerpts in the response. If the context is incomplete, the prompt tells the model to say what is uncertain instead of inventing details.

### 10. What happens if no relevant chunk is found?

Answer:

> The backend returns a fallback message telling the user that matching content could not be found in the uploaded PDFs yet.

### 11. How is data isolated per user?

Answer:

> Uploaded PDFs are stored in a user-specific directory, Chroma data is stored per user, and document IDs are validated against the current JWT identity before retrieval.

### 12. What database tables are used?

Answer:

> The main tables are `users`, `documents`, and `chat_messages`. Users hold auth data, documents store uploaded file metadata and chunk counts, and chat messages store question-answer history plus sources.

### 13. What is the role of the vector database here?

Answer:

> Chroma stores embeddings for each PDF chunk and lets the app retrieve the chunks most semantically similar to the user's question.

### 14. Why use Gemini embeddings and Gemini generation together?

Answer:

> Using the same provider simplifies integration and keeps the embedding and generation stack consistent for a student-friendly project.

### 15. What would you improve first?

Answer:

> I would add OCR and reranking first, because those would likely produce the biggest quality improvement for real-world documents.

## 16. If the interviewer asks "explain the project from frontend to backend"

Use this answer:

> The frontend is built with React and communicates with the Flask backend using Axios. A logged-in user can upload PDFs, see the indexed document list, select specific PDFs, and ask questions. The backend stores the PDF, extracts and cleans text, splits it into chunks, embeds those chunks using Gemini embeddings, and stores them in Chroma. On each question, the backend retrieves relevant chunks, builds a zero-shot prompt with recent memory and document context, sends it to Gemini `gemini-2.5-flash`, stores the answer in the database, and returns both the answer and source excerpts to the frontend.

## 17. If the interviewer asks "what makes this more than a demo?"

Use this answer:

> It has real full-stack structure: authentication, user-specific storage, persistent chat history, vector indexing, multi-document retrieval, source attribution, and configurable environment-based deployment. So it is small, but it already includes the main building blocks of a practical RAG application.

## 18. Best closing summary

If they ask for a summary, say:

> This project helped me understand the full RAG lifecycle end to end: ingestion, chunking, embeddings, vector storage, retrieval, prompt construction, grounded generation, and frontend delivery. It is not just calling an LLM API; it is a complete document-question-answering system with user isolation and retrieval-based reasoning.

## 19. Important repo-grounded facts to remember

- model used for answers: `gemini-2.5-flash`
- temperature used: `0.1`
- max output tokens: `1536`
- thinking budget: `256`
- embedding model: `gemini-embedding-2`
- chunk size: `1050` characters
- chunk overlap: `1` sentence
- MMR retrieval: `k=6`, `fetch_k=18`, `lambda_mult=0.65`
- similarity fallback: `k=8`
- recent memory in prompt: `5` messages
- chat history shown: `20` messages
- vector DB: Chroma
- prompting style: zero-shot with retrieved context

## 20. Parameters not explicitly configured in this repo

If they ask about other common LLM settings, say this honestly:

> In this project I explicitly configured model, temperature, max output tokens, and thinking budget. I did not explicitly configure settings like `top_p`, frequency penalty, presence penalty, or a reranker model in this version.

That is a good answer because it is accurate and shows you know the difference between what was implemented and what could be added later.

## 21. Where these answers came from in the codebase

- `backend/ragdocs_api/services/gemini_service.py`
- `backend/ragdocs_api/services/vector_store_service.py`
- `backend/ragdocs_api/services/pdf_service.py`
- `backend/ragdocs_api/services/chat_service.py`
- `backend/ragdocs_api/services/document_service.py`
- `backend/ragdocs_api/config.py`
- `backend/ragdocs_api/routes/chat.py`
- `backend/ragdocs_api/routes/documents.py`
- `frontend/src/hooks/useRagDocsApp.js`
- `README.md`

## 22. Best one-line answer if they ask "what did you personally build?"

> I built the end-to-end flow for a PDF RAG assistant: upload, chunking, embeddings, Chroma retrieval, Gemini answer generation, JWT-based user access, and a React UI that shows grounded answers with source excerpts.
