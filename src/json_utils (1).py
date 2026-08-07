"""
json_utils.py -- shared, robust JSON extraction from LLM text output.

Replaces the greedy `re.search(r"\{[\s\S]*\}")` pattern in
acronym_resolver.py: a greedy match grabs from the FIRST '{' to the LAST
'}' in the whole string, which breaks the moment the JSON contains nested
objects (e.g. a "metadata" field) followed by any trailing text. Same
contract as before -- returns None on failure, so existing except/fallback
branches in acronym_resolver.py trigger exactly as they did previously.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of the first well-formed top-level JSON
    object from arbitrary LLM text. Returns None if nothing parseable is
    found."""
    if not text:
        return None

    candidates = []
    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        candidates.append(fence_match.group(1))
    candidates.append(text)

    for candidate in candidates:
        obj = _first_balanced_object(candidate)
        if obj is not None:
            return obj
    return None


def _first_balanced_object(text: str) -> Optional[Dict[str, Any]]:
    """Find the first '{' and walk forward tracking brace depth (aware of
    string literals) until its true matching '}'. Falls back to searching
    further along the string if that first span isn't valid JSON."""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                snippet = text[start : i + 1]
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    return _first_balanced_object(text[i + 1:])

    return None
