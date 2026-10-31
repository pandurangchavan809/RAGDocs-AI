import json
import time

from flask import Blueprint, Response, jsonify, request, stream_with_context
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models import ChatMessage, Document
from ..services.chat_service import answer_question, stream_question
from ..services.llm_service import (
    AUTO_MODEL,
    get_auto_chain,
    get_available_models,
    is_selectable_model,
)
from ..utils.responses import error_response

chat_bp = Blueprint("chat", __name__)


@chat_bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@chat_bp.get("/config")
@jwt_required()
def config():
    return jsonify({"models": get_available_models(), "auto_models": get_auto_chain()})


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


def parse_chat_request(user_id):
    """Return (question, document_ids, model_id, error_response or None)."""
    data = request.get_json() or {}
    question = (data.get("question") or "").strip()
    document_ids = data.get("document_ids") or []
    model_id = data.get("model") or AUTO_MODEL

    if not question:
        return None, None, None, error_response("Question is required.")
    if not is_selectable_model(model_id):
        return None, None, None, error_response("The selected model is not available.")
    if not isinstance(document_ids, list):
        return None, None, None, error_response("document_ids must be a list.")

    try:
        document_ids = [int(item) for item in document_ids]
    except (TypeError, ValueError):
        return None, None, None, error_response("document_ids must contain valid IDs.")

    if document_ids:
        valid_document_count = Document.query.filter(
            Document.user_id == user_id, Document.id.in_(document_ids)
        ).count()
        if valid_document_count != len(document_ids):
            return (
                None,
                None,
                None,
                error_response("One or more selected documents are invalid.", 403),
            )

    return question, document_ids, model_id, None


def save_message(user_id, question, answer, document_ids, sources):
    message = ChatMessage(
        user_id=user_id,
        question=question,
        answer=answer,
        document_ids=json.dumps(document_ids),
        sources=json.dumps(sources),
    )
    db.session.add(message)
    db.session.commit()
    return message


def sse(event):
    return f"data: {json.dumps(event)}\n\n"


@chat_bp.post("/chat/stream")
@jwt_required()
def chat_stream():
    user_id = int(get_jwt_identity())
    question, document_ids, model_id, error = parse_chat_request(user_id)
    if error:
        return error

    def generate():
        started_at = time.perf_counter()
        tokens, sources = [], []
        try:
            for event in stream_question(user_id, question, document_ids, model_id):
                if event["type"] == "token":
                    tokens.append(event["text"])
                elif event["type"] == "sources":
                    sources = event["sources"]
                yield sse(event)

            # A client that stops early never reaches this point, so nothing is saved.
            message = save_message(
                user_id, question, "".join(tokens).strip(), document_ids, sources
            )
            yield sse(
                {
                    "type": "done",
                    "message_id": message.id,
                    "total_ms": round((time.perf_counter() - started_at) * 1000),
                }
            )
        except Exception as exc:
            yield sse({"type": "error", "error": f"RAG request failed: {exc}"})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@chat_bp.post("/chat")
@jwt_required()
def chat():
    user_id = int(get_jwt_identity())
    question, document_ids, model_id, error = parse_chat_request(user_id)
    if error:
        return error

    try:
        result = answer_question(user_id, question, document_ids, model_id)
    except Exception as exc:
        return error_response(f"RAG request failed: {exc}", 500)

    message = save_message(
        user_id, question, result["answer"], document_ids, result["sources"]
    )

    return jsonify(
        {
            "answer": result["answer"],
            "sources": result["sources"],
            "message_id": message.id,
            "model": result["model"],
        }
    )
