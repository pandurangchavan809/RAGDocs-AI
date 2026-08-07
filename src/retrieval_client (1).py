"""
retrieval_client.py -- the ONE place that knows how to call the embedding
and reranker servers. Mirrors llm_client.py's fallback-chain pattern
(config.settings.chain_for_task("EMBEDDING" / "RERANK")).

Scoped to dense-only for this version, matching retrieve.py's existing
embed_query()/rerank() contract exactly (embed_query returns a single
plain vector, not a dict of vector types) -- no behavior change to
retrieve.py's calling code, just the transport underneath it.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

import requests

from config import settings, Route

logger = logging.getLogger(__name__)


class RetrievalUnavailableError(RuntimeError):
    """Every route in the embedding/reranker fallback chain failed."""

    def __init__(self, service: str, attempts: List[Tuple[str, str]]):
        self.service = service
        self.attempts = attempts
        detail = "; ".join(f"{name}: {reason}" for name, reason in attempts)
        super().__init__(f"'{service}' unavailable -- every route failed ({detail})")


def _walk_chain(service: str, expected_kind: str, chain: List[Route], payload: dict) -> dict:
    attempts: List[Tuple[str, str]] = []
    for i, route in enumerate(chain):
        if route.kind != expected_kind:
            reason = f"route kind '{route.kind}' is not '{expected_kind}'"
            logger.warning("%s: route '%s' misconfigured -- %s", service, route.name, reason)
            attempts.append((route.name, reason))
            continue

        try:
            r = requests.post(route.url, json=payload, timeout=route.timeout)
            r.raise_for_status()
            data = r.json()
            if i > 0:
                logger.warning(
                    "%s: fell back to route '%s' after %d earlier failure(s)",
                    service, route.name, i,
                )
            return data
        except requests.exceptions.Timeout:
            reason = f"timed out after {route.timeout}s"
        except requests.exceptions.ConnectionError:
            reason = "unreachable"
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            reason = f"HTTP {status}"
        except Exception as e:
            reason = f"unexpected error: {e}"

        logger.warning("%s: route '%s' (%s) failed -- %s", service, route.name, route.url, reason)
        attempts.append((route.name, reason))

    raise RetrievalUnavailableError(service, attempts)


def embed_query(text: str) -> dict:
    """Encode a query, trying the embedding fallback chain in order.
    Returns the raw parsed response as a dict -- whichever of
    'dense' / 'sparse' / 'colbert' the embedding server actually provided.
    Only 'dense' is required; 'sparse' and 'colbert' may be None if the
    server/collection doesn't support them -- retrieve.py degrades
    gracefully in that case (dense-only, or dense+sparse without ColBERT
    reranking)."""
    chain = settings.chain_for_task("EMBEDDING")
    data = _walk_chain("EMBEDDING", "embed", chain, {"texts": [text]})

    dense_raw = data.get("dense") or data.get("embeddings")
    if not dense_raw:
        raise RetrievalUnavailableError(
            "EMBEDDING", [("(response parsing)", "no 'dense'/'embeddings' field in response")]
        )

    return {
        "dense": dense_raw[0],
        "sparse": data.get("sparse"),
        "colbert": data.get("colbert"),
    }


def rerank(query: str, passages: list) -> list:
    """Cross-encoder rerank, trying the reranker fallback chain in order."""
    chain = settings.chain_for_task("RERANK")
    data = _walk_chain("RERANK", "rerank", chain, {"query": query, "passages": passages})
    scores = data.get("scores")
    if scores is None:
        raise RetrievalUnavailableError(
            "RERANK", [("(response parsing)", "no 'scores' field in response")]
        )
    return scores
