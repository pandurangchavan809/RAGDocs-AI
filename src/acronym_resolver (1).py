import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config import settings
from llm_client import call_llm
from json_utils import extract_json_object
from .acronym_db import AcronymDB


@dataclass
class CandidateMeaning:
    meaning: Dict[str, Any]
    confidence: float


class AcronymResolver:
    def __init__(self, db: AcronymDB):
        self.db = db

    def resolve(self, acronym: str, context: str) -> Dict[str, Any]:
        entries = self.db.get_entries(acronym)
        candidates = []
        for e in entries:
            candidates.append({
                "fullForm": e.get("fullForm", ""),
                "description": (e.get("description", "") or "")[:500],
                "category": e.get("category", ""),
                "metadata": e.get("metadata", {}),
            })

        # Instant resolution: if there is exactly 1 candidate in DB, use it without calling the LLM
        if len(candidates) == 1:
            best = {
                "meaning": {
                    "fullForm": candidates[0]["fullForm"],
                    "description": candidates[0].get("description", ""),
                },
                "confidence": 1.0
            }
            return {
                "status": "auto_selected",
                "acronym": acronym,
                "selected": best,
                "top2": [best],
                "policy": "Single database match (auto-selected instantly)",
            }

        # Prompt depends on whether candidates exist in database
        if not candidates:
            # Case 1: Acronym not in database -> ask LLM to guess the 2 most likely meanings
            prompt = (
                "You are an automotive acronym disambiguation assistant.\n"
                f"The acronym '{acronym}' was not found in the database. Based on the surrounding context, please generate the top 2 most likely meanings for it.\n"
                "Guidelines:\n"
                "- Research your general knowledge to generate the most widely accepted full forms and descriptions for this acronym in the automotive/semiconductor industry.\n"
                "- Descriptions must be a concise, 1-2 sentence explanation of what this component does.\n"
                "- Assign a HIGH confidence score if this is a standard, widely-known term with one clear, "
                "unambiguous meaning in this domain (e.g. a common industry acronym) -- do not lowball a "
                "confident answer just because it wasn't in the database.\n"
                "- Assign a LOW confidence score only when the acronym is genuinely ambiguous, could plausibly "
                "mean several different things in this context, or you are not actually sure.\n\n"
                f"SURROUNDING CONTEXT:\n{context}\n\n"
                "Output MUST be a single JSON object with this exact schema:\n"
                "{\n"
                "  \"acronym\": \"" + acronym + "\",\n"
                "  \"top2\": [\n"
                "    {\"meaning\": {\"fullForm\": \"<meaning 1>\", \"description\": \"<description 1>\"}, \"confidence\": <number 0-1>},\n"
                "    {\"meaning\": {\"fullForm\": \"<meaning 2>\", \"description\": \"<description 2>\"}, \"confidence\": <number 0-1>}\n"
                "  ]\n"
                "}\n"
            )
        else:
            # Case 2: Acronym exists in database -> choose correct one from candidates
            prompt = (
                "You are an automotive acronym disambiguation assistant. "
                "Given an acronym and surrounding user context, choose the most likely meanings.\n"
                "Guidelines:\n"
                "- Match the category (e.g., automotive SoC, display technologies, networks) and select candidates that fit perfectly with the surrounding words and context.\n"
                "- If the context has strong indicators matching a candidate's description, assign a high confidence score.\n"
                "- If none of the candidates match the context well, assign low confidence scores (below 0.5) so that the system will prompt the user.\n\n"
                f"ACRONYM: {acronym}\n\n"
                f"SURROUNDING CONTEXT:\n{context}\n\n"
                "CANDIDATES (JSON array). Each candidate has a possible meaning: fullForm + description.\n"
                f"{json.dumps(candidates, ensure_ascii=False)}\n\n"
                "TASK:\n"
                "- Pick the top 2 candidate meanings that best match the context.\n"
                "- Provide a confidence score between 0 and 1 for each of the 2 selections.\n"
                "- Output MUST be a single JSON object with this exact schema:\n"
                "{\n"
                "  \"acronym\": \"" + acronym + "\",\n"
                "  \"top2\": [\n"
                "    {\"meaning\": {\"fullForm\": \"<meaning 1>\", \"description\": \"<description 1>\"}, \"confidence\": <number 0-1>},\n"
                "    {\"meaning\": {\"fullForm\": \"<meaning 2>\", \"description\": \"<description 2>\"}, \"confidence\": <number 0-1>}\n"
                "  ]\n"
                "}\n"
            )

        try:
            raw = call_llm(
                task="ACRONYM_RESOLVE",
                prompt=prompt,
                system="Return only the required JSON schema.",
                max_tokens=512,
            )
            parsed = extract_json_object(raw)
            if not parsed:
                raise RuntimeError(f"Un-parseable JSON output: {raw[:300]}")
            top2 = parsed.get("top2") or []
            top2_sorted = sorted(top2, key=lambda x: float(x.get("confidence", 0.0)), reverse=True)[:2]
        except Exception as e:
            print(f"[AcronymResolver] Acronym lookup LLM call failed, using rule-based fallback: {e}")
            if len(candidates) == 1:
                top2_sorted = [{
                    "meaning": {
                        "fullForm": candidates[0]["fullForm"],
                        "description": candidates[0].get("description", ""),
                    },
                    "confidence": 1.0
                }]
            elif len(candidates) > 1:
                top2_sorted = []
                for c in candidates[:2]:
                    top2_sorted.append({
                        "meaning": {
                            "fullForm": c["fullForm"],
                            "description": c.get("description", ""),
                        },
                        "confidence": 0.7 if len(top2_sorted) == 0 else 0.6
                    })
            else:
                top2_sorted = []

        # Normalize confidence to 0-1 floats
        norm_top2 = []
        for item in top2_sorted:
            meaning = item.get("meaning") or {}
            norm_top2.append({
                "meaning": {
                    "fullForm": meaning.get("fullForm", ""),
                    "description": meaning.get("description", ""),
                },
                "confidence": float(item.get("confidence", 0.0)),
            })

        # Apply policies
        if not norm_top2:
            return {
                "status": "needs_user_provide",
                "acronym": acronym,
                "top2": [],
                "policy": "No database entry and LLM unavailable"
            }

        best = norm_top2[0]
        best_conf = float(best["confidence"]) * 100.0

        auto_thr = settings.acronym_confidence_auto
        choice_thr = settings.acronym_confidence_choice

        if candidates:
            # Found in database: two-tier confidence
            if best_conf >= auto_thr:
                return {
                    "status": "auto_selected",
                    "acronym": acronym,
                    "selected": best,
                    "top2": norm_top2,
                    "policy": f"Found in database & confidence >= {int(auto_thr)}%",
                }
            elif best_conf >= choice_thr:
                return {
                    "status": "needs_user_choice",
                    "acronym": acronym,
                    "top2": norm_top2,
                    "policy": f"Found in database & confidence {int(choice_thr)}-{int(auto_thr)}%",
                }
            else:
                return {
                    "status": "needs_user_provide",
                    "acronym": acronym,
                    "top2": norm_top2,
                    "policy": f"Found in database & confidence < {int(choice_thr)}%",
                }
        else:
            # Not found in database: previously this ALWAYS forced HITL
            # regardless of confidence -- even when the LLM was highly
            # confident it could infer the meaning from context (e.g.
            # "DMIPS" -> "Dhrystone Million Instructions Per Second", a
            # standard term any reasonable model already knows). Route
            # through the SAME confidence tiers as in-database candidates
            # instead of a hardcoded HITL every time.
            if best_conf >= auto_thr:
                return {
                    "status": "auto_selected",
                    "acronym": acronym,
                    "selected": best,
                    "top2": norm_top2,
                    "policy": f"Not in database, but confidently inferred from context >= {int(auto_thr)}%",
                }
            elif best_conf >= choice_thr:
                return {
                    "status": "needs_user_choice",
                    "acronym": acronym,
                    "top2": norm_top2,
                    "policy": f"Not in database, confidence {int(choice_thr)}-{int(auto_thr)}%",
                }
            else:
                return {
                    "status": "needs_user_provide",
                    "acronym": acronym,
                    "top2": norm_top2,
                    "policy": f"Not in database, confidence < {int(choice_thr)}%",
                }
