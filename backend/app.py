import json
import os
import re
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)

from flask_sqlalchemy import SQLAlchemy
from google import genai
from google.genai import types
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from PyPDF2 import PdfReader
from sqlalchemy.exc import OperationalError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
CHROMA_DIR = BASE_DIR / "storage" / "chroma"
INDEX_VERSION = "ragdocs_v2"

load_dotenv(BASE_DIR / ".env")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)


def build_database_uri():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return database_url

    mysql_host = os.getenv("MYSQL_HOST", "").strip()
    mysql_port = os.getenv("MYSQL_PORT", "3306").strip()
    mysql_user = os.getenv("MYSQL_USER", "").strip()
    mysql_password = os.getenv("MYSQL_PASSWORD", "")
    mysql_database = os.getenv("MYSQL_DATABASE", "").strip()

    if all([mysql_host, mysql_user, mysql_database]):
        encoded_password = quote_plus(mysql_password)
        return (
            f"mysql+pymysql://{mysql_user}:{encoded_password}"
            f"@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4"
        )

    return f"sqlite:///{BASE_DIR / 'ragdocs.db'}"


def get_env_float(name, default):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def get_env_int(name, default):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def build_engine_options():
    database_uri = build_database_uri()
    options = {
        "pool_pre_ping": True,
        "pool_recycle": get_env_int("DB_POOL_RECYCLE_SECONDS", 240),
    }

    if database_uri.startswith("mysql+pymysql://"):
        options["pool_timeout"] = get_env_int("DB_POOL_TIMEOUT_SECONDS", 30)
        if os.getenv("MYSQL_SSL_MODE", "").strip().upper() == "REQUIRED":
            options["connect_args"] = {"ssl": {}}

    return options


@lru_cache(maxsize=1)
def get_gemini_config():
    return {
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        "temperature": get_env_float("GEMINI_TEMPERATURE", 0.1),
        "max_output_tokens": get_env_int("GEMINI_MAX_OUTPUT_TOKENS", 1536),
        "thinking_budget": get_env_int("GEMINI_THINKING_BUDGET", 256),
    }


def get_gemini_api_key():
    return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()


@lru_cache(maxsize=1)
def get_gemini_client():
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError(
            "Set GEMINI_API_KEY or GOOGLE_API_KEY in backend/.env before using chat."
        )
    return genai.Client(api_key=api_key)


def get_gemini_generation_config():
    config = get_gemini_config()
    return types.GenerateContentConfig(
        temperature=config["temperature"],
        max_output_tokens=config["max_output_tokens"],
        thinking_config=types.ThinkingConfig(
            thinking_budget=config["thinking_budget"]
        ),
        response_mime_type="text/plain",
    )


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = build_database_uri()
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = build_engine_options()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "change-this-secret")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

CORS(app, resources={r"/api/*": {"origins": os.getenv("FRONTEND_URL", "*")}})
db = SQLAlchemy(app)
jwt = JWTManager(app)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    chunk_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    document_ids = db.Column(db.Text, default="[]")
    sources = db.Column(db.Text, default="[]")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


def error_response(message, status_code=400):
    return jsonify({"error": message}), status_code


@app.errorhandler(OperationalError)
def handle_operational_error(error):
    db.session.remove()
    return error_response(
        "Database connection was interrupted. Please try again.",
        503,
    )


def allowed_file(filename):
    return "." in filename and filename.lower().endswith(".pdf")


class GeminiEmbeddings(Embeddings):
    def __init__(self, model_name):
        self.model_name = model_name

    def _embed_text(self, text):
        client = get_gemini_client()
        response = client.models.embed_content(
            model=self.model_name,
            contents=text,
        )
        return response.embeddings[0].values

    def embed_documents(self, texts):
        return [self._embed_text(f"title: pdf chunk | text: {text}") for text in texts]

    def embed_query(self, text):
        return self._embed_text(f"task: question answering | query: {text}")


@lru_cache(maxsize=1)
def get_embedding_model():
    return GeminiEmbeddings(
        model_name=os.getenv("EMBEDDING_MODEL", "gemini-embedding-2").strip()
    )


def get_embedding_collection_name():
    model_name = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2").strip()
    safe_name = model_name.replace("-", "_").replace("/", "_")
    return f"documents_{safe_name}_{INDEX_VERSION}"


def get_vector_store(user_id):
    user_store_dir = CHROMA_DIR / f"user_{user_id}"
    user_store_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=get_embedding_collection_name(),
        persist_directory=str(user_store_dir),
        embedding_function=get_embedding_model(),
    )


def normalize_pdf_text(text):
    text = text.replace("\x00", " ").replace("\u00a0", " ")
    raw_lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    paragraphs = []
    current = []

    for line in raw_lines:
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue

        current.append(line)
        if line.endswith((".", "!", "?", ":", ";")) and len(" ".join(current)) >= 120:
            paragraphs.append(" ".join(current))
            current = []

    if current:
        paragraphs.append(" ".join(current))

    cleaned_paragraphs = [
        paragraph for paragraph in paragraphs if is_meaningful_text(paragraph, 10)
    ]
    return "\n\n".join(cleaned_paragraphs).strip()


def is_meaningful_text(text, min_words=18):
    words = re.findall(r"[A-Za-z]{2,}", text)
    if len(words) < min_words:
        return False

    letters = sum(char.isalpha() for char in text)
    total = max(len(text), 1)
    return letters / total >= 0.45


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def extract_pdf_pages(file_path):
    reader = PdfReader(str(file_path))
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        cleaned_text = normalize_pdf_text(page.extract_text() or "")
        if cleaned_text:
            pages.append({"page_number": page_number, "text": cleaned_text})

    return pages


def split_text(pages):
    max_chunk_chars = 1050
    overlap_sentences = 1
    chunks = []

    for page in pages:
        paragraphs = [part.strip() for part in page["text"].split("\n\n") if part.strip()]
        current_sentences = []
        current_length = 0

        for paragraph in paragraphs:
            sentences = split_sentences(paragraph) or [paragraph]
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                sentence_length = len(sentence) + 1
                if current_sentences and current_length + sentence_length > max_chunk_chars:
                    chunk_text = " ".join(current_sentences).strip()
                    if is_meaningful_text(chunk_text):
                        chunks.append(
                            {
                                "page_number": page["page_number"],
                                "text": chunk_text,
                            }
                        )
                    current_sentences = current_sentences[-overlap_sentences:]
                    current_length = sum(len(item) + 1 for item in current_sentences)

                current_sentences.append(sentence)
                current_length += sentence_length

        if current_sentences:
            chunk_text = " ".join(current_sentences).strip()
            if is_meaningful_text(chunk_text):
                chunks.append(
                    {
                        "page_number": page["page_number"],
                        "text": chunk_text,
                    }
                )

    return chunks


def delete_document_chunks(store, document_id):
    existing = store.get(where={"document_id": str(document_id)}, include=[])
    existing_ids = existing.get("ids") or []
    if existing_ids:
        store.delete(ids=existing_ids)


def store_document_chunks(user_id, document_id, document_name, chunks):
    store = get_vector_store(user_id)
    delete_document_chunks(store, document_id)

    ids = []
    texts = []
    metadatas = []

    for index, chunk in enumerate(chunks):
        ids.append(f"doc-{document_id}-chunk-{index}")
        texts.append(chunk["text"])
        metadatas.append(
            {
                "user_id": str(user_id),
                "document_id": str(document_id),
                "filename": document_name,
                "chunk_index": index,
                "page_number": chunk["page_number"],
                "index_version": INDEX_VERSION,
            }
        )

    if texts:
        store.add_texts(texts=texts, metadatas=metadatas, ids=ids)


def get_user_documents(user_id, document_ids=None):
    query = Document.query.filter_by(user_id=user_id)
    if document_ids:
        query = query.filter(Document.id.in_(document_ids))
    return query.order_by(Document.created_at.desc()).all()


def document_needs_reindex(store, document):
    result = store.get(
        where={"document_id": str(document.id)},
        limit=1,
        include=["metadatas"],
    )
    ids = result.get("ids") or []
    if not ids:
        return True

    metadata_list = result.get("metadatas") or []
    if not metadata_list:
        return True

    return metadata_list[0].get("index_version") != INDEX_VERSION


def ensure_documents_indexed(user_id, document_ids=None):
    store = get_vector_store(user_id)
    documents = get_user_documents(user_id, document_ids)
    changed = False

    for document in documents:
        if not document_needs_reindex(store, document):
            continue

        file_path = UPLOAD_DIR / str(user_id) / document.stored_name
        if not file_path.exists():
            continue

        pages = extract_pdf_pages(file_path)
        chunks = split_text(pages)
        store_document_chunks(user_id, document.id, document.original_name, chunks)

        if document.chunk_count != len(chunks):
            document.chunk_count = len(chunks)
            db.session.add(document)
            changed = True

    if changed:
        db.session.commit()


def get_recent_memory(user_id, limit=5):
    messages = (
        ChatMessage.query.filter_by(user_id=user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    history_lines = []
    for item in reversed(messages):
        history_lines.append(f"User: {item.question}")
        history_lines.append(f"Assistant: {item.answer}")
    return "\n".join(history_lines)


def build_source_payload(documents):
    seen = set()
    sources = []

    for doc in documents:
        source_key = (
            doc.metadata.get("document_id"),
            doc.metadata.get("chunk_index"),
        )
        if source_key in seen:
            continue
        seen.add(source_key)
        sources.append(
            {
                "document_id": doc.metadata.get("document_id"),
                "filename": doc.metadata.get("filename", "Unknown PDF"),
                "chunk_index": doc.metadata.get("chunk_index", 0),
                "page_number": doc.metadata.get("page_number"),
                "excerpt": doc.page_content[:260].strip(),
            }
        )

    return sources


def retrieve_relevant_chunks(user_id, question, document_ids=None):
    store = get_vector_store(user_id)
    search_filter = None
    if document_ids:
        search_filter = {"document_id": {"$in": [str(item) for item in document_ids]}}

    documents = []

    try:
        documents.extend(
            store.max_marginal_relevance_search(
                question,
                k=6,
                fetch_k=18,
                lambda_mult=0.65,
                filter=search_filter,
            )
        )
    except Exception:
        pass

    try:
        scored_documents = store.similarity_search_with_score(
            question,
            k=8,
            filter=search_filter,
        )
        documents.extend([doc for doc, _score in scored_documents])
    except Exception:
        if not documents:
            documents.extend(store.similarity_search(question, k=8, filter=search_filter))

    seen = set()
    unique_documents = []
    for doc in documents:
        key = (
            doc.metadata.get("document_id"),
            doc.metadata.get("chunk_index"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_documents.append(doc)

    filtered_documents = [
        doc for doc in unique_documents if is_meaningful_text(doc.page_content)
    ]
    return (filtered_documents or unique_documents)[:6]


def answer_question(user_id, question, document_ids=None):
    ensure_documents_indexed(user_id, document_ids)
    documents = retrieve_relevant_chunks(user_id, question, document_ids)

    if not documents:
        return {
            "answer": "I could not find matching content in your uploaded PDFs yet. Upload a document or ask about a different section.",
            "sources": [],
        }

    context = "\n\n".join(
        [
            (
                f"[Source {index + 1} | {doc.metadata.get('filename', 'PDF')} | "
                f"Page {doc.metadata.get('page_number', '?')}]\n{doc.page_content}"
            )
            for index, doc in enumerate(documents)
        ]
    )
    memory = get_recent_memory(user_id)

    prompt = f"""
You are RAGDocs AI, a helpful PDF assistant.
Answer only from the provided PDF context.
Write one clear, complete answer in plain English.
Ignore broken fragments, repeated template text, author lists, page headers, and partial lines unless they directly answer the question.
If the question is about the whole document, first summarize the main purpose in 2-4 sentences, then add short key points.
If the context is incomplete, say what is clear and what is uncertain.
Do not invent details that are not supported by the context.

Recent conversation:
{memory or "No recent conversation."}

Document context:
{context}

Question:
{question}
""".strip()

    client = get_gemini_client()
    config = get_gemini_config()
    response = client.models.generate_content(
        model=config["model"],
        contents=prompt,
        config=get_gemini_generation_config(),
    )
    answer = (response.text or "").strip()
    if not answer:
        raise ValueError("Gemini returned an empty response.")

    return {"answer": answer, "sources": build_source_payload(documents)}


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/auth/register")
def register():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return error_response("Name, email, and password are required.")

    if User.query.filter_by(email=email).first():
        return error_response("An account with this email already exists.", 409)

    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "Account created successfully. Please log in.",
                "user": {"id": user.id, "name": user.name, "email": user.email},
            }
        ),
        201,
    )


@app.post("/api/auth/login")
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return error_response("Invalid email or password.", 401)

    token = create_access_token(identity=str(user.id))
    return jsonify(
        {
            "token": token,
            "user": {"id": user.id, "name": user.name, "email": user.email},
        }
    )


@app.get("/api/documents")
@jwt_required()
def list_documents():
    user_id = int(get_jwt_identity())
    documents = get_user_documents(user_id)
    return jsonify(
        [
            {
                "id": doc.id,
                "name": doc.original_name,
                "chunk_count": doc.chunk_count,
                "created_at": doc.created_at.isoformat(),
            }
            for doc in documents
        ]
    )


@app.post("/api/documents/upload")
@jwt_required()
def upload_document():
    user_id = int(get_jwt_identity())
    file = request.files.get("file")

    if not file or not file.filename:
        return error_response("Please choose a PDF file.")
    if not allowed_file(file.filename):
        return error_response("Only PDF files are supported.")

    original_name = secure_filename(file.filename)
    stored_name = f"{uuid.uuid4().hex}.pdf"
    user_upload_dir = UPLOAD_DIR / str(user_id)
    user_upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_upload_dir / stored_name
    file.save(file_path)

    pages = extract_pdf_pages(file_path)
    chunks = split_text(pages)
    if not chunks:
        file_path.unlink(missing_ok=True)
        return error_response("No readable text was found in this PDF.")

    document = Document(
        user_id=user_id,
        original_name=original_name,
        stored_name=stored_name,
        chunk_count=len(chunks),
    )
    db.session.add(document)
    db.session.commit()

    store_document_chunks(user_id, document.id, original_name, chunks)

    return (
        jsonify(
            {
                "message": "PDF uploaded and indexed successfully.",
                "document": {
                    "id": document.id,
                    "name": document.original_name,
                    "chunk_count": document.chunk_count,
                },
            }
        ),
        201,
    )


@app.get("/api/chat/history")
@jwt_required()
def chat_history():
    user_id = int(get_jwt_identity())
    messages = (
        ChatMessage.query.filter_by(user_id=user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify(
        [
            {
                "id": message.id,
                "question": message.question,
                "answer": message.answer,
                "document_ids": json.loads(message.document_ids or "[]"),
                "sources": json.loads(message.sources or "[]"),
                "created_at": message.created_at.isoformat(),
            }
            for message in reversed(messages)
        ]
    )


@app.delete("/api/chat/history")
@jwt_required()
def clear_chat_history():
    user_id = int(get_jwt_identity())
    ChatMessage.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"message": "Chat history cleared successfully."})


@app.post("/api/chat")
@jwt_required()
def chat():
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    question = (data.get("question") or "").strip()
    document_ids = data.get("document_ids") or []

    if not question:
        return error_response("Question is required.")
    if not isinstance(document_ids, list):
        return error_response("document_ids must be a list.")

    try:
        document_ids = [int(item) for item in document_ids]
    except (TypeError, ValueError):
        return error_response("document_ids must contain valid IDs.")

    if document_ids:
        valid_document_count = Document.query.filter(
            Document.user_id == user_id, Document.id.in_(document_ids)
        ).count()
        if valid_document_count != len(document_ids):
            return error_response("One or more selected documents are invalid.", 403)

    try:
        result = answer_question(user_id, question, document_ids)
    except Exception as exc:
        return error_response(f"RAG request failed: {exc}", 500)

    message = ChatMessage(
        user_id=user_id,
        question=question,
        answer=result["answer"],
        document_ids=json.dumps(document_ids),
        sources=json.dumps(result["sources"]),
    )
    db.session.add(message)
    db.session.commit()

    return jsonify(
        {
            "answer": result["answer"],
            "sources": result["sources"],
            "message_id": message.id,
        }
    )


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
