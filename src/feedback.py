"""
feedback.py -- persist per-answer like/dislike feedback to a JSON file.

Backing file: <project_root>/feedback.json  (NOT inside src/ -- lives at the
project root, next to app.py, acc.json, etc.)

Each entry mirrors what session_report.py stores per turn (question, answer,
retrieved chunks/sources) plus a feedback type and a timestamp:

    {
      "question": "...",
      "answer": "...",
      "sources": [ {"doc_id": "...", "pages": "...", "kind": "...",
                     "score": 0.83, "text": "..."}, ... ],
      "feedback": "like" | "dislike",
      "date": "2026-07-15",
      "time": "14:32:07",
      "timestamp": "2026-07-15T14:32:07.123456"
    }

Usage from app.py:

    from src.feedback import add_feedback
    add_feedback(question, answer, sources, liked)   # liked: bool
"""
import json
from pathlib import Path
from threading import Lock
from datetime import datetime

# src/feedback.py -> parent.parent is the project root -> feedback.json
FEEDBACK_PATH = Path(__file__).resolve().parent.parent / "feedback.json"

_lock = Lock()


def _load():
    if not FEEDBACK_PATH.exists():
        return []
    try:
        content = FEEDBACK_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        return []
    if not content:
        return []
    try:
        data = json.loads(content)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save(data):
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _chunk_view(s):
    """Normalize one retrieved chunk/source dict to a compact, consistent shape."""
    if not isinstance(s, dict):
        return {"doc_id": "?", "pages": "?", "kind": "", "score": None, "text": str(s)}
    return {
        "doc_id": s.get("doc_id", s.get("source_file", s.get("source", "?"))),
        "pages":  s.get("pages", "?"),
        "kind":   s.get("kind", ""),
        "score":  s.get("score"),
        "text":   s.get("text", ""),
    }


def add_feedback(question, answer, sources=None, liked=True):
    """Record one like/dislike event. `liked` can be a bool, or the strings
    'like'/'dislike'/'up'/'down' -- anything falsy or 'dislike'/'down' counts
    as a dislike, everything else counts as a like."""
    if isinstance(liked, str):
        feedback_type = "dislike" if liked.strip().lower() in ("dislike", "down", "no", "false") else "like"
    else:
        feedback_type = "like" if liked else "dislike"

    now = datetime.now()
    entry = {
        "question": question or "",
        "answer": answer or "",
        "sources": [_chunk_view(s) for s in (sources or [])],
        "feedback": feedback_type,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timestamp": now.isoformat(),
    }

    with _lock:
        data = _load()
        data.append(entry)
        _save(data)

    return entry


def all_feedback():
    return _load()


def likes():
    return [e for e in _load() if e.get("feedback") == "like"]


def dislikes():
    return [e for e in _load() if e.get("feedback") == "dislike"]


if __name__ == "__main__":
    data = _load()
    print(f"{FEEDBACK_PATH}: {len(data)} entr{'y' if len(data)==1 else 'ies'} "
          f"({len(likes())} like, {len(dislikes())} dislike)")
