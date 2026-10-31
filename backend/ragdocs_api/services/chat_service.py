import time

from ..models import ChatMessage
from .document_service import ensure_documents_indexed
from .llm_service import AUTO_MODEL, get_model_label, stream_answer
from .pdf_service import is_meaningful_text
from .vector_store_service import get_embedding_model, get_vector_store


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


def retrieve_relevant_chunks(user_id, query_embedding, document_ids=None):
    store = get_vector_store(user_id)
    search_filter = None
    if document_ids:
        search_filter = {"document_id": {"$in": [str(item) for item in document_ids]}}

    documents = []

    try:
        documents.extend(
            store.max_marginal_relevance_search_by_vector(
                query_embedding,
                k=6,
                fetch_k=18,
                lambda_mult=0.65,
                filter=search_filter,
            )
        )
    except Exception:
        pass

    try:
        documents.extend(
            store.similarity_search_by_vector(
                query_embedding,
                k=8,
                filter=search_filter,
            )
        )
    except Exception:
        if not documents:
            raise

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


def build_prompt(user_id, question, documents):
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

    return f"""
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


def step_event(step_id, label, status, started_at=None, detail=None):
    event = {"type": "step", "id": step_id, "label": label, "status": status}
    if started_at is not None:
        event["duration_ms"] = round((time.perf_counter() - started_at) * 1000)
    if detail:
        event["detail"] = detail
    return event


def stream_question(user_id, question, document_ids=None, model_id=AUTO_MODEL):
    """Run the RAG pipeline, yielding each real stage and answer token as it happens."""
    ensure_documents_indexed(user_id, document_ids)

    label = "Embedding query"
    yield step_event("embed", label, "running")
    started_at = time.perf_counter()
    query_embedding = get_embedding_model().embed_query(question)
    yield step_event("embed", label, "done", started_at)

    label = "Retrieving context"
    yield step_event("retrieve", label, "running")
    started_at = time.perf_counter()
    documents = retrieve_relevant_chunks(user_id, query_embedding, document_ids)
    file_count = len({doc.metadata.get("document_id") for doc in documents})
    yield step_event(
        "retrieve",
        label,
        "done",
        started_at,
        f"{len(documents)} {'chunk' if len(documents) == 1 else 'chunks'} from {file_count} "
        f"{'document' if file_count == 1 else 'documents'}",
    )

    if not documents:
        yield {
            "type": "token",
            "text": "I could not find matching content in your uploaded PDFs yet. Upload a document or ask about a different section.",
        }
        return

    yield {"type": "sources", "sources": build_source_payload(documents)}

    prompt = build_prompt(user_id, question, documents)
    step_id = label = started_at = None
    attempt = 0
    for event in stream_answer(prompt, model_id):
        if event["type"] == "model_start":
            attempt += 1
            step_id = f"llm-{attempt}"
            label = f"Sending to {get_model_label(event['model'])}"
            started_at = time.perf_counter()
            yield step_event(step_id, label, "running")
            current_model = event["model"]
        elif event["type"] == "model_failed":
            yield step_event(
                step_id, label, "error", started_at, "Failed before answering"
            )
            started_at = None
        else:
            if started_at is not None:
                # The step ends at the first token: the model has started answering.
                yield step_event(step_id, label, "done", started_at)
                yield {"type": "model", "model": current_model}
                started_at = None
            yield event


def answer_question(user_id, question, document_ids=None, model_id=AUTO_MODEL):
    tokens, sources, model = [], [], None
    for event in stream_question(user_id, question, document_ids, model_id):
        if event["type"] == "token":
            tokens.append(event["text"])
        elif event["type"] == "sources":
            sources = event["sources"]
        elif event["type"] == "model":
            model = event["model"]

    return {"answer": "".join(tokens).strip(), "sources": sources, "model": model}


