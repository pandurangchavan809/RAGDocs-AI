"""
config.py -- single source of truth for every runtime setting.

Every other module imports from here instead of calling os.getenv()
directly. Adding a server, moving a job to a different model, or adding a
fallback should only ever require editing .env -- never this file, and
never the module that consumes the setting.

--------------------------------------------------------------------------
ROUTES
--------------------------------------------------------------------------
A "route" is one deployed server: where it lives, what it speaks, how
long to wait for it.

    ROUTE_<NAME>_URL       (required)
    ROUTE_<NAME>_KIND      (required: "generate" | "openai_chat" | "embed" | "rerank")
    ROUTE_<NAME>_MODEL     (required only for kinds that need a model name, e.g. openai_chat)
    ROUTE_<NAME>_TIMEOUT   (optional, seconds, default 120)

<NAME> is a role label (PRIMARY / SECONDARY / LOCAL), never a model name --
swapping the model behind a route is a value edit, never a rename.

--------------------------------------------------------------------------
TASK -> ROUTE CHAINS
--------------------------------------------------------------------------
Every job reads an ORDERED, comma-separated chain of route names:

    TASK_RAG_ANSWER_ROUTES=LLM_PRIMARY,LLM_SECONDARY,LLM_LOCAL
    TASK_AGENT_EVAL_ROUTES=LLM_SECONDARY,LLM_LOCAL
    TASK_ACRONYM_RESOLVE_ROUTES=LLM_SECONDARY,LLM_LOCAL
    TASK_EMBEDDING_ROUTES=EMBED_PRIMARY,EMBED_LOCAL
    TASK_RERANK_ROUTES=RERANK_PRIMARY,RERANK_LOCAL

Qwen3.6 (LLM_PRIMARY) intentionally appears ONLY in TASK_RAG_ANSWER_ROUTES
-- every other task's chain deliberately excludes it, so the final answer
is the only place its reasoning overhead and larger token budget matter.

This module fails fast (raises ConfigError) on missing/invalid settings
rather than silently guessing a default.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent

VALID_KINDS = {"generate", "openai_chat", "embed", "rerank"}
_KINDS_NEEDING_MODEL = {"openai_chat"}


class ConfigError(RuntimeError):
    """Missing or invalid configuration -- meant to stop the app at
    startup, not be caught and papered over."""


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name}={raw!r} is not a valid integer")


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(f"{name}={raw!r} is not a valid float")


def _split_chain(raw: str) -> List[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


@dataclass(frozen=True)
class Route:
    name: str
    url: str
    kind: str
    model: Optional[str]
    timeout: int
    enable_thinking: Optional[bool] = None  # None = don't send the kwarg at all (server default)

    def __post_init__(self):
        if self.kind not in VALID_KINDS:
            raise ConfigError(
                f"ROUTE_{self.name}_KIND={self.kind!r} invalid -- must be one of {sorted(VALID_KINDS)}"
            )
        if self.kind in _KINDS_NEEDING_MODEL and not self.model:
            raise ConfigError(
                f"ROUTE_{self.name}_MODEL is required when KIND={self.kind!r} "
                f"(the server needs a model name in the request body)"
            )


_ROUTE_URL_RE = re.compile(r"^ROUTE_(.+)_URL$")


def _parse_bool(raw: str, name: str) -> bool:
    val = raw.strip().lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    raise ConfigError(f"{name}={raw!r} is not a valid boolean (use true/false)")


def _discover_routes() -> Dict[str, Route]:
    routes: Dict[str, Route] = {}
    for key in os.environ:
        m = _ROUTE_URL_RE.match(key)
        if not m:
            continue
        name = m.group(1)
        url = os.environ[key].strip()
        kind = os.getenv(f"ROUTE_{name}_KIND", "").strip()
        model = os.getenv(f"ROUTE_{name}_MODEL", "").strip() or None
        timeout = _get_int(f"ROUTE_{name}_TIMEOUT", 120)
        enable_thinking_raw = os.getenv(f"ROUTE_{name}_ENABLE_THINKING", "").strip()
        enable_thinking = _parse_bool(enable_thinking_raw, f"ROUTE_{name}_ENABLE_THINKING") if enable_thinking_raw else None
        if not url:
            raise ConfigError(f"ROUTE_{name}_URL is set but empty")
        if not kind:
            raise ConfigError(f"ROUTE_{name}_URL is set but ROUTE_{name}_KIND is missing")
        routes[name] = Route(name=name, url=url, kind=kind, model=model, timeout=timeout,
                              enable_thinking=enable_thinking)
    return routes


class Settings:
    def __init__(self):
        self.routes: Dict[str, Route] = _discover_routes()
        if not self.routes:
            raise ConfigError(
                "No ROUTE_*_URL entries found in .env -- at least one route "
                "must be defined before the app can start."
            )

        # ---- Retrieval pipeline (switchable via .env -- this is the
        # "multi-collection support": no code edit needed to point at a
        # different Qdrant path/collection) ----
        self.qdrant_path = os.getenv("QDRANT_DB_PATH", "qdrant_db_vlm")
        self.qdrant_collection = os.getenv("QDRANT_COLLECTION", "rag_chunks_vlm")
        self.candidates = _get_int("CANDIDATES", 30)
        self.top_k = _get_int("TOP_K", 10)
        self.threshold = _get_float("THRESHOLD", 0.0)

        # ---- Generation limits ----
        self.max_chunk_chars = _get_int("MAX_CHUNK_CHARS", 1200)
        self.max_context_chars = _get_int("MAX_CONTEXT_CHARS", 12000)
        self.max_new_tokens = _get_int("MAX_NEW_TOKENS", 2048)
        # Separate, larger budget for the final RAG_ANSWER call only --
        # Qwen3.6's <think> trace needs room the eval/acronym calls don't.
        self.rag_answer_max_new_tokens = _get_int("RAG_ANSWER_MAX_NEW_TOKENS", 6000)
        self.llm_temperature = _get_float("LLM_TEMPERATURE", 0.2)

        # ---- Acronym / HITL ----
        # Two-tier, matching .env: >=AUTO auto-selects, CHOICE-AUTO asks
        # the user to pick, <CHOICE asks the user to provide it outright.
        self.acronym_confidence_auto = _get_float("ACRONYM_CONFIDENCE_AUTO", 90.0)
        self.acronym_confidence_choice = _get_float("ACRONYM_CONFIDENCE_CHOICE", 60.0)
        self.hitl_countdown_seconds = _get_int("HITL_COUNTDOWN_SECONDS", 30)
        self.acronyms_sys_path = os.getenv("ACRONYMS_SYS_PATH", "acronyms/clean_35.json")
        self.acronyms_user_path = os.getenv("ACRONYMS_USER_PATH", "acc.json")

        # ---- Multi-vector retrieval field names ----
        # Dense is auto-detected from the collection itself (see
        # retrieve.py's _dense_vector_name()); these two are only read if
        # the embed server/collection actually provides them -- retrieval
        # degrades gracefully to dense-only / dense+sparse when absent.
        self.sparse_vector_name = os.getenv("SPARSE_VECTOR_NAME", "sparse")
        self.colbert_vector_name = os.getenv("COLBERT_VECTOR_NAME", "colbert")

        # ---- Agent ----
        self.agent_max_iterations = _get_int("AGENT_MAX_ITERATIONS", 2)

    def chain_for_task(self, task: str) -> List[Route]:
        """task, e.g. 'RAG_ANSWER', 'AGENT_EVAL', 'ACRONYM_RESOLVE',
        'EMBEDDING', 'RERANK'. Reads TASK_<task>_ROUTES=<NAME1>,<NAME2>,...
        (ordered, first = primary)."""
        env_key = f"TASK_{task}_ROUTES"
        raw = os.getenv(env_key)
        if not raw:
            raise ConfigError(
                f"{env_key} is not set in .env -- every task needs an explicit, "
                f"ordered route chain (e.g. 'LLM_PRIMARY,LLM_LOCAL')."
            )
        chain = []
        for name in _split_chain(raw):
            route = self.routes.get(name)
            if route is None:
                raise ConfigError(
                    f"{env_key} references undefined route '{name}'. "
                    f"Known routes: {sorted(self.routes)}"
                )
            chain.append(route)
        return chain

    def rag_answer_route_names(self) -> List[str]:
        """Route names for the final-answer model-picker dropdown -- just
        the configured TASK_RAG_ANSWER_ROUTES chain, in order. Whatever a
        user picks is used as `preferred_route` in llm_client.call_llm(),
        which still falls back through this same chain underneath it."""
        return [r.name for r in self.chain_for_task("RAG_ANSWER")]

    def sanitized_startup_summary(self) -> str:
        """Safe-to-log summary (URLs/kinds/models only, no secrets)."""
        lines = ["Loaded routes:"]
        for name, r in sorted(self.routes.items()):
            lines.append(f"  {name}: kind={r.kind} url={r.url} model={r.model or '-'} timeout={r.timeout}s")
        return "\n".join(lines)


settings = Settings()
