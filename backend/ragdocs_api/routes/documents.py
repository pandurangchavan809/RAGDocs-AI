import uuid

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.utils import secure_filename

from ..config import UPLOAD_DIR
from ..extensions import db
from ..models import Document
from ..services.document_service import get_user_documents, store_document_chunks
from ..services.pdf_service import allowed_file, extract_pdf_pages, split_text
from ..utils.responses import error_response

documents_bp = Blueprint("documents", __name__)


@documents_bp.get("/documents")
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


@documents_bp.post("/documents/upload")
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
