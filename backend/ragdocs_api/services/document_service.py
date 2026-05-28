from ..config import INDEX_VERSION, UPLOAD_DIR
from ..extensions import db
from ..models import Document
from .pdf_service import extract_pdf_pages, split_text
from .vector_store_service import get_vector_store


def get_user_documents(user_id, document_ids=None):
    query = Document.query.filter_by(user_id=user_id)
    if document_ids:
        query = query.filter(Document.id.in_(document_ids))
    return query.order_by(Document.created_at.desc()).all()


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
