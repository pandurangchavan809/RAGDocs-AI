import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models import ChatMessage, Document
from ..services.chat_service import answer_question
from ..utils.responses import error_response

chat_bp = Blueprint("chat", __name__)


@chat_bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@chat_bp.get("/chat/history")
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


@chat_bp.delete("/chat/history")
@jwt_required()
def clear_chat_history():
    user_id = int(get_jwt_identity())
    ChatMessage.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"message": "Chat history cleared successfully."})


@chat_bp.post("/chat")
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
