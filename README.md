# RAGDocs AI

RAGDocs AI is a small full-stack starter for a RAG-based PDF assistant. It is intentionally simple and student-friendly while still covering the important features:

- JWT authentication
- user-specific PDF uploads
- PDF chunking and embeddings
- Chroma vector search
- Gemini-powered answers
- saved chat memory
- multi-document querying
- source excerpts in the UI

## Stack

- Frontend: React + Vite + Tailwind CSS + Axios
- Backend: Flask + SQLAlchemy + Flask-JWT-Extended
- RAG: LangChain + Google Gemini API + Gemini embeddings + ChromaDB
- Database: SQLite by default for easy learning, or MySQL with `DATABASE_URL`

## Project Structure

```text
backend/
  app.py
  requirements.txt
  .env.example
frontend/
  src/
  package.json
  .env.example
```

## Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Set these values in `backend/.env`:

```env
DATABASE_URL=sqlite:///ragdocs.db
JWT_SECRET_KEY=replace-with-a-secret-key
GEMINI_API_KEY=your-gemini-api-key
GOOGLE_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.1
GEMINI_MAX_OUTPUT_TOKENS=1536
GEMINI_THINKING_BUDGET=256
EMBEDDING_MODEL=gemini-embedding-2
FRONTEND_URL=http://localhost:5173
```

If you want MySQL instead of SQLite, set either a single `DATABASE_URL` or the separate MySQL fields:

```env
DATABASE_URL=mysql+pymysql://username:password@localhost/ragdocs_ai
```

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=username
MYSQL_PASSWORD=password
MYSQL_DATABASE=ragdocs_ai
MYSQL_SSL_MODE=REQUIRED
DB_POOL_RECYCLE_SECONDS=240
DB_POOL_TIMEOUT_SECONDS=30
```

For your Aiven setup, the schema file now targets `defaultdb`.

1. Fill the real Aiven password into `backend/.env`
2. Run the schema import script:

```bash
cd backend
python import_mysql_schema.py
```

Then run the Flask app normally:

```bash
python app.py
```

## Frontend Setup

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

## Main API Endpoints

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/documents`
- `POST /api/documents/upload`
- `GET /api/chat/history`
- `POST /api/chat`

## Notes

- PDFs are stored per user in `backend/storage/uploads/`
- embeddings are stored per user in `backend/storage/chroma/`
- chat memory is saved in the SQL database
- leaving all documents unchecked lets the assistant search across every uploaded PDF
- the backend now uses Google’s official `google-genai` SDK with Gemini `gemini-2.5-flash`
- embeddings now default to Google `gemini-embedding-2`
- Gemini 2.5 reasoning is configured with `GEMINI_THINKING_BUDGET`

## Why This Version Is Simpler

- The Flask backend stays in one main file so it is easy to follow.
- The React frontend uses one main page instead of a complex route setup.
- SQLite is the default so the project works faster for learning, but MySQL is still supported through `DATABASE_URL`.
- The UI is dark, compact, and readable without extra animation or unnecessary components.
