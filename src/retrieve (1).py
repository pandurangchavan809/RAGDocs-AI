"""
retrieve.py -- multi-vector retrieval for the document chunk DB.

Dense + sparse are RRF-fused for recall. ColBERT (if the active
collection/embed server actually provides it) reranks that SAME pool
afterwards -- it never joins the fusion vote. Letting ColBERT vote
alongside dense/sparse let it dominate/skew results in earlier testing;
reranking-only avoids that while still using it when available.

Every stage degrades gracefully based on what's actually present for a
given query/collection:
    dense + sparse + colbert -> RRF recall, then ColBERT rerank
    dense + sparse           -> RRF recall only
    dense only                -> plain dense query (today's common case)

Safety nets kept exactly as before: if retrieval fails entirely (embed
server down, Qdrant error, etc.), fall back to a keyword search over the
acronym DB rather than returning nothing; if reranking fails, proceed
with the recall-stage scores instead of raising.
"""
import atexit
import sys

from qdrant_client import QdrantClient, models

from config import settings, PROJECT_ROOT
from retrieval_client import embed_query, rerank

QDRANT_PATH = PROJECT_ROOT / settings.qdrant_path
COLLECTION = settings.qdrant_collection

CANDIDATES = settings.candidates
TOP_K = settings.top_k
THRESHOLD = settings.threshold

SPARSE_NAME = settings.sparse_vector_name
COLBERT_NAME = settings.colbert_vector_name

client = QdrantClient(path=str(QDRANT_PATH))
atexit.register(client.close)


def _dense_vector_name(client, collection):
    """Figure out how the dense vector is stored so the query matches the index."""
    try:
        vectors = client.get_collection(collection).config.params.vectors
        if isinstance(vectors, dict):
            return "dense" if "dense" in vectors else next(iter(vectors.keys()))
    except Exception:
        return "dense"
    return None


def _registered_vector_names(client, collection):
    """What the TARGET COLLECTION itself actually has registered for
    dense/multivector and sparse fields -- read once at startup, the same
    way DENSE_NAME already is.

    This matters if you run a single shared embed endpoint that always
    returns dense+sparse+colbert regardless of which collection you're
    about to query: without this check, retrieve() would trust the embed
    response and try to query e.g. "colbert" against a collection that
    never registered that field, Qdrant would raise, and the outer
    try/except would silently divert to the acronym-DB fallback -- a
    'wrong path taken' failure that's harder to notice than a clean error,
    since it looks like it worked. Cross-checking against the collection's
    real schema means sparse/colbert are only ever attempted when BOTH the
    embed response AND the collection itself support them."""
    try:
        info = client.get_collection(collection)
        vec_names = set(info.config.params.vectors.keys()) if isinstance(info.config.params.vectors, dict) else set()
        sparse_names = set(info.config.params.sparse_vectors.keys()) if info.config.params.sparse_vectors else set()
        return vec_names, sparse_names
    except Exception:
        return set(), set()


DENSE_NAME: str | None = _dense_vector_name(client, COLLECTION)
_REGISTERED_VECTOR_NAMES, _REGISTERED_SPARSE_NAMES = _registered_vector_names(client, COLLECTION)
COLLECTION_SUPPORTS_SPARSE = SPARSE_NAME in _REGISTERED_SPARSE_NAMES
COLLECTION_SUPPORTS_COLBERT = COLBERT_NAME in _REGISTERED_VECTOR_NAMES

print(f"[retrieve] Qdrant path={QDRANT_PATH} collection={COLLECTION} "
      f"dense_field={DENSE_NAME or '(default/unnamed)'} "
      f"sparse_field={SPARSE_NAME} (registered={COLLECTION_SUPPORTS_SPARSE}) "
      f"colbert_field={COLBERT_NAME} (registered={COLLECTION_SUPPORTS_COLBERT})")


def _row(score, payload, width=120):
    """One-line view of a chunk for the verbose dump."""
    val = payload.get("text")
    text_str = "" if (val is None or (isinstance(val, float) and val != val)) else str(val)
    text = text_str.replace("\n", " ")
    return (f"[{score:.3f} | p{payload.get('pages')} | "
            f"{payload.get('kind')}] {text[:width]}")


def _dedup(hits, verbose=False):
    """Drop chunks whose text is identical (keep the first / best-ranked)."""
    seen, kept = set(), []
    for h in hits:
        val = h.payload.get("text")
        key = "" if (val is None or (isinstance(val, float) and val != val)) else str(val).strip()
        if key in seen:
            continue
        seen.add(key)
        kept.append(h)
    if verbose and len(kept) < len(hits):
        print(f"  (dedup: removed {len(hits) - len(kept)} identical chunk(s))")
    return kept


def _build_sparse_vector(sparse_raw):
    """embed_query() returns sparse as either a single {'indices','values'}
    dict or a one-item list containing it, depending on the server."""
    if not sparse_raw:
        return None
    first = sparse_raw[0] if isinstance(sparse_raw, list) else sparse_raw
    if not first or "indices" not in first or "values" not in first:
        return None
    return models.SparseVector(indices=first["indices"], values=first["values"])


def _build_colbert_vector(colbert_raw):
    """embed_query() returns colbert as either a single token-vector matrix
    ([[...],[...],...]) or a one-item list containing it."""
    if not colbert_raw:
        return None
    if isinstance(colbert_raw[0], list) and colbert_raw[0] and isinstance(colbert_raw[0][0], list):
        return colbert_raw[0]
    return colbert_raw


def _build_recall_prefetches(dense, sparse_vec, candidates):
    """RECALL stage -- dense and/or sparse, fused by RRF if both present.
    ColBERT is never a branch here (see module docstring): it reranks
    this pool afterwards instead of voting on it."""
    prefetches = []
    if dense is not None:
        prefetches.append(models.Prefetch(query=dense, using=DENSE_NAME, limit=candidates))
    if sparse_vec is not None:
        prefetches.append(models.Prefetch(query=sparse_vec, using=SPARSE_NAME, limit=candidates))
    return prefetches


def _run_recall_and_colbert_rerank(recall_prefetches, colbert_vec, candidates, verbose=False):
    """Runs the recall stage (dense+sparse RRF, or whichever of the two is
    present), then -- only if a ColBERT vector was actually returned for
    this query -- reranks that exact pool with it."""
    if not recall_prefetches:
        return []

    if colbert_vec is not None:
        if len(recall_prefetches) > 1:
            inner = models.Prefetch(
                prefetch=recall_prefetches,
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=candidates,
            )
        else:
            inner = recall_prefetches[0]

        if verbose:
            print("  (ColBERT reranking the dense+sparse recall pool -- not joining fusion)")

        return client.query_points(
            collection_name=COLLECTION,
            prefetch=[inner],
            query=colbert_vec,
            using=COLBERT_NAME,
            limit=candidates,
            with_payload=True,
        ).points

    if len(recall_prefetches) > 1:
        return client.query_points(
            collection_name=COLLECTION,
            prefetch=recall_prefetches,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=candidates,
            with_payload=True,
        ).points

    # Exactly one branch available (dense-only, the common case today, or
    # sparse-only) -- no fusion wrapper needed, query it directly.
    only = recall_prefetches[0]
    return client.query_points(
        collection_name=COLLECTION,
        query=only.query,
        using=only.using,
        limit=candidates,
        with_payload=True,
    ).points


def _fallback_acronym_db_retrieve(query, top_k):
    from src.acronym_db import AcronymDB
    db = AcronymDB()

    import re
    tokens = re.findall(r"[A-Za-z0-9+\-]{2,}", query)
    db_entries = db.all()

    matched_entries = []
    seen_acr = set()
    for t in tokens:
        t_clean = t.strip().lower()
        for e in db_entries:
            acr = str(e.get("acronym") or "").strip()
            if acr.lower() == t_clean and acr.lower() not in seen_acr:
                matched_entries.append(e)
                seen_acr.add(acr.lower())

    if not matched_entries:
        query_words = [w.lower() for w in tokens if len(w) > 2]
        scored_entries = []
        for e in db_entries:
            text_to_search = (
                str(e.get("acronym") or "") + " " +
                str(e.get("fullForm") or "") + " " +
                str(e.get("description") or "")
            ).lower()
            score = 0
            for qw in query_words:
                if qw in text_to_search:
                    score += 1
            if score > 0:
                scored_entries.append((e, score))
        scored_entries.sort(key=lambda x: x[1], reverse=True)
        matched_entries = [x[0] for x in scored_entries[:top_k]]

    matched_entries = matched_entries[:top_k]

    results = []
    for i, e in enumerate(matched_entries, 1):
        acr = e.get("acronym")
        ff = e.get("fullForm")
        desc = e.get("description", "")
        category = e.get("category", "")

        text = f"Acronym: {acr}\nFull Form: {ff}\nCategory: {category}\nDescription: {desc}\nAttributes:\n"
        metadata = e.get("metadata") or {}
        for k, v in metadata.items():
            text += f"{k}={v}\n"

        results.append({
            "score": 1.0 - (0.05 * (i - 1)),
            "doc_id": "System Acronym DB" if e.get("category") != "User Provided" else "User Acronym DB",
            "pages": "1",
            "kind": "text",
            "text": text.strip()
        })

    return results


def retrieve(query, top_k=TOP_K, candidates=CANDIDATES, threshold=THRESHOLD, verbose=False):
    try:
        emb = embed_query(query)
        dense = emb.get("dense")
        # Only attempt sparse/colbert if the TARGET COLLECTION actually
        # registered that field -- not just because the embed response
        # happened to include it (see _registered_vector_names() above).
        sparse_vec = _build_sparse_vector(emb.get("sparse")) if COLLECTION_SUPPORTS_SPARSE else None
        colbert_vec = _build_colbert_vector(emb.get("colbert")) if COLLECTION_SUPPORTS_COLBERT else None

        if verbose:
            present = ", ".join(
                name for name, v in (("dense", dense), ("sparse", sparse_vec), ("colbert", colbert_vec)) if v is not None
            ) or "(none)"
            print(f"\n=== vectors present for this query: {present} ===")

        recall_prefetches = _build_recall_prefetches(dense, sparse_vec, candidates)
        if not recall_prefetches:
            print("ERROR: embed server returned no usable dense/sparse vector for this query.")
            return []

        hits = _run_recall_and_colbert_rerank(recall_prefetches, colbert_vec, candidates, verbose=verbose)
    except Exception as e:
        print(f"[Retrieve] Retrieval failed: {e}. Falling back to Acronym DB search.")
        return _fallback_acronym_db_retrieve(query, top_k=top_k)

    if not hits:
        if verbose:
            print("\n=== RETRIEVED: nothing came back from Qdrant ===")
        return []

    # Sanitize payload text to be strings, handling float/NaN values
    for h in hits:
        if h.payload:
            val = h.payload.get("text")
            h.payload["text"] = "" if (val is None or (isinstance(val, float) and val != val)) else str(val)

    hits = _dedup(hits, verbose=verbose)

    if verbose:
        print(f"\n=== RETRIEVED ({len(hits)} unique candidates after recall/ColBERT stage) ===")
        for h in hits:
            print("  " + _row(h.score, h.payload))

    try:
        scores = rerank(query, [h.payload["text"] for h in hits])
        ranked = sorted(zip(hits, scores), key=lambda x: x[1], reverse=True)
    except Exception as e:
        print(f"[Retrieve] Reranking failed: {e}. Proceeding with original recall-stage scores.")
        ranked = sorted(zip(hits, [float(h.score) for h in hits]), key=lambda x: x[1], reverse=True)

    kept_ids, count = set(), 0
    for h, s in ranked:
        if s >= threshold and count < top_k:
            kept_ids.add(id(h))
            count += 1

    if verbose:
        print(f"\n=== FINAL RERANK ({len(ranked)} scored | threshold={threshold} | top_k={top_k}) ===")
        for h, s in ranked:
            if id(h) in kept_ids:
                tag = "KEPT       "
            elif s < threshold:
                tag = "drop <thr  "
            else:
                tag = "drop >top_k"
            print(f"  {tag} " + _row(s, h.payload))
        print(f"\n--> {len(kept_ids)} chunk(s) passed to the LLM\n")

    kept = [(h, s) for h, s in ranked if id(h) in kept_ids]
    return [{"score": float(s), **h.payload} for h, s in kept]


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "How many TOPS does the Dragonwing IQ9 deliver?"
    print(f"\nQuery: {q}")
    print(f"(candidates={CANDIDATES}, top_k={TOP_K}, threshold={THRESHOLD})")
    retrieve(q, verbose=True)
    client.close()
