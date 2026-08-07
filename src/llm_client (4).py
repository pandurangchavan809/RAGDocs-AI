"""
llm_client.py -- the ONE place that knows how to talk to an LLM route.

Every existing LLM call site (agent.py's eval call and final-answer call,
acronym_resolver.py's resolution call) is replaced with a call to
call_llm(task=..., ...) instead of its own requests.post() -- the
surrounding logic (fallback-to-rule-based on failure, local_fallback_generate,
etc.) is untouched; only the transport changes.

FALLBACK BEHAVIOR
------------------
Each task is bound to an ORDERED CHAIN of routes (config.settings.
chain_for_task). call_llm tries the first route; if it's unreachable,
times out, or returns something unparseable, it logs the failure and moves
to the next route in the chain. Only when every route in the chain has
failed does call_llm raise LLMUnavailableError -- callers already have
their own try/except around these calls (e.g. agent.py's fallback to
local_fallback_generate) and LLMUnavailableError is just a RuntimeError,
so those existing except blocks catch it exactly as before with zero
changes needed there.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

import requests

from config import settings, Route

logger = logging.getLogger(__name__)

_LLM_KINDS = {"generate", "openai_chat"}

# Fallback safety net: strips a raw, unparsed reasoning trace from
# 'content' when the server ISN'T splitting it into a separate
# reasoning_content field (see _call_openai_chat below for the primary
# fix -- suppressing thinking at the source via chat_template_kwargs).
#
# IMPORTANT: for Qwen3-family models, the <think> OPENING tag is injected
# into the PROMPT by the chat template -- it is not part of what the model
# generates. So a raw completion often has NO literal opening tag at all,
# just a bare closing </think> partway through, e.g.:
#     "<reasoning text with no leading tag>\n</think>\n\n<the real answer>"
# Requiring both tags to match (the old approach) silently let this
# straight through. The correct rule (matching vLLM's own
# qwen3_reasoning_parser): split on the closing tag alone -- everything
# before it is reasoning, everything after is the answer, whether or not
# an opening tag is present.
_THINK_CLOSE_RE = re.compile(r"</think>", re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think>", re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    if not text:
        return text

    close_match = _THINK_CLOSE_RE.search(text)
    if close_match:
        return text[close_match.end():].strip()

    # No closing tag. If an opening tag is present with nothing closing
    # it, generation was cut off mid-reasoning (token budget too small
    # for this task) -- there's no safe answer text to return.
    if _THINK_OPEN_RE.search(text):
        logger.warning(
            "Unterminated <think> block (no </think> found) -- response "
            "was likely truncated before the real answer; consider "
            "raising this task's token budget."
        )
        return ""

    # No think tags at all -- either a non-reasoning model, or the server
    # already suppressed thinking at the source. No-op, unchanged.
    return text.strip()


class LLMUnavailableError(RuntimeError):
    """Every route in the task's fallback chain failed."""

    def __init__(self, task: str, attempts: List[Tuple[str, str]]):
        self.task = task
        self.attempts = attempts
        detail = "; ".join(f"{name}: {reason}" for name, reason in attempts)
        super().__init__(f"'{task}' unavailable -- every route in the chain failed ({detail})")


def _call_generate(route: Route, prompt: str, system: Optional[str], max_tokens: int) -> str:
    payload = {"prompt": prompt, "max_new_tokens": max_tokens}
    if system:
        payload["system"] = system

    r = requests.post(route.url, json=payload, timeout=route.timeout)
    r.raise_for_status()
    data = r.json()

    text = data.get("response") or data.get("text") or data.get("generated_text")
    if not text:
        raise ValueError("no usable text field (expected response/text/generated_text)")
    return str(text).strip()


def _call_openai_chat(route: Route, prompt: str, system: Optional[str],
                       max_tokens: int, temperature: float) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": route.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    # PRIMARY fix for thinking-trace leakage: tell the chat template not
    # to enter thinking mode at all, rather than stripping it after the
    # fact. Only sent if ROUTE_<name>_ENABLE_THINKING is actually set in
    # .env -- omitted entirely for routes that don't set it, so this never
    # breaks an openai_chat endpoint that doesn't recognize the kwarg.
    if route.enable_thinking is not None:
        payload["chat_template_kwargs"] = {"enable_thinking": route.enable_thinking}

    r = requests.post(route.url, json=payload, timeout=route.timeout)
    r.raise_for_status()
    data = r.json()

    try:
        message = data["choices"][0]["message"]
        content = str(message["content"]).strip()
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"unexpected openai_chat response shape: {e}")

    # If the server was launched with a reasoning parser (e.g. vLLM/SGLang
    # --reasoning-parser qwen3), thinking arrives as a SEPARATE field --
    # 'content' is already clean. Explicitly discard reasoning_content
    # rather than silently ignoring it, so it's visible in logs which
    # server config is actually running.
    reasoning_content = message.get("reasoning_content")
    if reasoning_content:
        logger.info(
            "route '%s': server returned separate reasoning_content (%d chars, discarded) -- "
            "this server IS using a reasoning parser; 'content' should already be clean.",
            route.name, len(str(reasoning_content)),
        )

    return content


def call_llm(
    task: str,
    prompt: str,
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    preferred_route: Optional[str] = None,
) -> str:
    """
    task: e.g. "RAG_ANSWER", "AGENT_EVAL", "ACRONYM_RESOLVE" -- resolved to
    an ORDERED CHAIN of routes via TASK_<task>_ROUTES in .env.

    preferred_route: optional route name (from the UI model picker) to try
    first within that SAME chain -- does not change which routes are
    eligible, only their trial order.

    Raises LLMUnavailableError only if every route in the chain fails.
    """
    chain = settings.chain_for_task(task)
    chain = _reorder_for_preference(chain, preferred_route)

    max_tokens = max_tokens if max_tokens is not None else settings.max_new_tokens
    temperature = temperature if temperature is not None else settings.llm_temperature

    attempts: List[Tuple[str, str]] = []

    for i, route in enumerate(chain):
        if route.kind not in _LLM_KINDS:
            reason = f"route kind '{route.kind}' is not an LLM kind (expected generate/openai_chat)"
            logger.warning("task=%s: route '%s' misconfigured -- %s", task, route.name, reason)
            attempts.append((route.name, reason))
            continue

        try:
            if route.kind == "generate":
                result = _call_generate(route, prompt, system, max_tokens)
            else:
                result = _call_openai_chat(route, prompt, system, max_tokens, temperature)

            result = _strip_thinking(result)

            if i > 0:
                logger.warning(
                    "task=%s: fell back to route '%s' after %d earlier failure(s)",
                    task, route.name, i,
                )
            else:
                logger.info("task=%s: answered by route '%s' (%s)", task, route.name, route.kind)
            return result

        except requests.exceptions.Timeout:
            reason = f"timed out after {route.timeout}s"
        except requests.exceptions.ConnectionError:
            reason = "unreachable"
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            reason = f"HTTP {status}"
        except ValueError as e:
            reason = str(e)
        except Exception as e:
            reason = f"unexpected error: {e}"

        logger.warning("task=%s: route '%s' (%s) failed -- %s", task, route.name, route.url, reason)
        attempts.append((route.name, reason))

    raise LLMUnavailableError(task, attempts)


def _reorder_for_preference(chain: List[Route], preferred_route: Optional[str]) -> List[Route]:
    if not preferred_route:
        return chain
    preferred_route = preferred_route.strip()
    match_idx = next((i for i, r in enumerate(chain) if r.name.lower() == preferred_route.lower()), None)
    if match_idx is None:
        logger.warning(
            "preferred_route '%s' is not part of this task's configured chain -- ignoring.",
            preferred_route,
        )
        return chain
    return [chain[match_idx]] + [r for i, r in enumerate(chain) if i != match_idx]


def is_task_configured(task: str) -> bool:
    """Config-level check only -- confirms a route chain is assigned.
    Does NOT probe the network."""
    try:
        settings.chain_for_task(task)
        return True
    except Exception:
        return False
