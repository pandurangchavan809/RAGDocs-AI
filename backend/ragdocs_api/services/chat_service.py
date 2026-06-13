from ..models import ChatMessage
from .document_service import ensure_documents_indexed
from .gemini_service import (
    get_gemini_client,
    get_gemini_config,
    get_gemini_generation_config,
)
from .pdf_service import is_meaningful_text
from .vector_store_service import get_vector_store


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


