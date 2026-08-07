"""
rag.py -- retrieval + generation glue.

NOTE: answer_ex() below delegates entirely to AgenticSearch -- the
generate()/build_context()/build_prompt() functions in this file are not
currently called by anything (that's true in your original version too).
Kept working and centralized (routed through call_llm like everything
else) in case this file is ever used as a direct, non-agentic entry point.
"""
import sys

from config import settings
from llm_client import call_llm
from src.retrieve import retrieve

MAX_CHUNK_CHARS = settings.max_chunk_chars
MAX_CONTEXT_CHARS = settings.max_context_chars
MAX_NEW_TOKENS = settings.max_new_tokens

# ---------------------------------------------------------------------------
# PROMPT  (natural-language replies, exact figures, clean spacing, citation)
# -- left exactly as-is, not touched --
# ---------------------------------------------------------------------------
SYSTEM = """You are a technical-documentation assistant for automotive and semiconductor spec \
+sheets. Answer the user's question using ONLY the context passages, each tagged like \
+[Some Doc p.15].


- When a passage contains "Attributes=...", treat it as multiple key-value pairs.
- ALWAYS match the user's query to the EXACT attribute key (e.g., "Video Encode", "Video Decode").
- Extract ONLY the value corresponding to that exact attribute.
- NEVER mix values from different attributes, even if they appear in the same row.
- If multiple attributes are present, ignore all others and return only the matching one

A "table" or "table row" passage is an extracted table; columns labelled 0, 1, 2 are unnamed \
columns from the source file -- infer their meaning from the values. The answer may span more \
than one passage.

Reply like a knowledgeable colleague answering the question out loud:
- Write complete, natural sentences. Begin by naming the subject, e.g. "The SA7255P supports ...".
- Report values EXACTLY as written -- every number, unit and part number unchanged. Weave them \
into your wording; never paste raw table fragments, column dumps, or run-together text.
- If the question matches several items, variants, rows or models, list EACH one with its own \
value -- do not collapse them into a single figure. Completeness beats brevity here.
- Report only what each passage states. Do not aggregate, average, total, or reduce several \
distinct values to one, and never write "up to", "around" or "about" unless the passage itself \
uses that word or gives that range.
- Where the extraction lost spacing (e.g. "16MP4xCSI2"), write it cleanly ("16 MP, 4x CSI-2") \
without changing any value.
- Cite using the bracketed tag that precedes each passage, copied verbatim, e.g. [Some Doc p.15].
- If the answer is not in the passages, reply exactly: Not found in the provided documents.

Be as brief as the question allows, but never drop a value to stay short. Cite ONLY the bracketed \
tags -- never invent a citation or refer to a passage by number."""

KIND_LABEL = {"text": "text", "table_full": "table", "table_row": "table row"}


def _fmt_pages(pages):
    if pages is None:
        return "p.?"
    if isinstance(pages, (list, tuple)):
        pages = [str(p) for p in pages if p is not None]
        return "p." + ", ".join(pages) if pages else "p.?"
    return f"p.{pages}"


def _tag(c):
    return f"[{c.get('doc_id', '?')} {_fmt_pages(c.get('pages'))}]"


def build_context(chunks):
    blocks, used = [], 0
    for c in chunks:
        kind = KIND_LABEL.get(c.get("kind"), c.get("kind") or "text")
        val = c.get("text")
        text = "" if (val is None or (isinstance(val, float) and val != val)) else str(val).strip()
        if len(text) > MAX_CHUNK_CHARS:
            text = text[:MAX_CHUNK_CHARS].rstrip() + " ..."
        block = f"{_tag(c)} ({kind})\n{text}"
        if used + len(block) > MAX_CONTEXT_CHARS and blocks:
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)


def build_prompt(query, chunks, history_context: str | None = None):
    """Build user-side prompt content.

    history_context is short memory text (last 5 summaries + last user message)
    that the app wants the model to consider.

    SYSTEM is sent separately.
    """
    hist = (history_context or "").strip()
    hist_block = "" if not hist else f"Conversation memory (cache):\n{hist}\n\n"

    return (
        f"{hist_block}"
        f"Context (passages ordered most relevant first):\n{build_context(chunks)}\n\n"
        f"Question: {query}"
    )


# ---------------------------------------------------------------------------
# GENERATION  (via llm_client -- route-chained, format-agnostic; Qwen3.6
# lives here too since this is the RAG_ANSWER task, same as agent.py's
# final-answer call)
# ---------------------------------------------------------------------------

def generate(prompt):
    text = call_llm(task="RAG_ANSWER", prompt=prompt, system=SYSTEM, max_tokens=settings.rag_answer_max_new_tokens)
    for p in ("Answer:", "A:"):
        if text.startswith(p):
            text = text[len(p):].strip()
    return text


def _sources_view(chunks):
    out = []
    for i, c in enumerate(chunks, 1):
        val = c.get("text")
        t = "" if (val is None or (isinstance(val, float) and val != val)) else str(val).strip()
        out.append(
            {
                "rank": i,
                "score": round(float(c.get("score", 0.0)), 3),
                "doc_id": c.get("doc_id", "?"),
                "pages": _fmt_pages(c.get("pages")),
                "kind": c.get("kind", "text"),
                "text": t[:600] + (" ..." if len(t) > 600 else ""),
            }
        )
    return out


def answer_ex(query, show_prompt=False, show_sources=False, history_context: str | None = None):
    """Returns {'answer': str, 'sources': [...]} -- used by the web UI."""
    from src.agent import AgenticSearch
    agent = AgenticSearch()
    return agent.run(query, history_context)


def answer(query, show_prompt=False, show_sources=False, history_context: str | None = None):
    return answer_ex(query, show_prompt=show_prompt, show_sources=show_sources, history_context=history_context)["answer"]


if __name__ == "__main__":
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        ans = answer(q, show_prompt=True, show_sources=True)
        print(f"\nQ: {q}\n\nBot: {ans}")
    else:
        print("\nRAG chatbot ready. Ask a question ('quit' to stop).")
        while True:
            q = input("\nYou: ").strip()
            if q.lower() in {"quit", "exit", ""}:
                break
            ans = answer(q, show_prompt=True, show_sources=True)
            print(f"\nBot: {ans}")
