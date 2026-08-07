import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config import settings


@dataclass
class PendingAcronym:
    token: str
    acronym: str
    context: str
    top2: list
    created_at: float
    status: str  # needs_user_choice | needs_user_provide
    resolved: Optional[Dict[str, Any]] = None


class HitlAcronymFlow:
    """In-memory human-in-the-loop state.

    IMPORTANT: construct this class exactly ONCE per process. Use the
    module-level `hitl_flow` singleton below in every route/module --
    never call HitlAcronymFlow() directly elsewhere. Two separate
    instances means a token created via one route can never be resolved
    via another (this was a real, confirmed bug: app.py's /resolve_acronym
    and /acronym_feedback routes used to hold two different instances).
    """

    def __init__(self, timeout_seconds: int = 60):
        self.timeout_seconds = timeout_seconds
        self._pending: Dict[str, PendingAcronym] = {}

    def create(self, acronym: str, context: str, top2: list, status: str) -> PendingAcronym:
        token = uuid.uuid4().hex
        p = PendingAcronym(
            token=token,
            acronym=acronym,
            context=context,
            top2=top2,
            created_at=time.time(),
            status=status,
        )
        self._pending[token] = p
        return p

    def get(self, token: str) -> Optional[PendingAcronym]:
        return self._pending.get(token)

    def _timed_out(self, p: PendingAcronym) -> bool:
        return (time.time() - p.created_at) > self.timeout_seconds

    def assume_best_if_timeout(self, token: str) -> Optional[Dict[str, Any]]:
        p = self._pending.get(token)
        if not p:
            return None
        if self._timed_out(p):
            if p.top2:
                best = p.top2[0]
                resolved = {
                    "source": "timeout_assumed_best",
                    "acronym": p.acronym,
                    "meaning": best["meaning"],
                    "confidence": best["confidence"],
                }
            else:
                resolved = {
                    "source": "timeout_assumed_best",
                    "acronym": p.acronym,
                    "meaning": {"fullForm": "", "description": ""},
                    "confidence": 0.0,
                }
            self._pending.pop(token, None)
            return resolved
        return None

    def sweep_expired(self) -> List[Dict[str, Any]]:
        """Auto-resolve every pending token that has exceeded its timeout,
        assuming the best-ranked candidate for each. Returns the list of
        resolved results. There is no background scheduler in this
        single-process app -- call this opportunistically (e.g. once per
        incoming /chat request) so abandoned HITL prompts don't sit in
        memory forever (previously: assume_best_if_timeout existed but was
        never called from anywhere)."""
        resolved = []
        for token in list(self._pending.keys()):
            r = self.assume_best_if_timeout(token)
            if r is not None:
                resolved.append(r)
        return resolved

    def resolve_choice(self, token: str, choice_index: int) -> Dict[str, Any]:
        p = self._pending.get(token)
        if not p:
            raise KeyError("invalid pending token")

        if choice_index < 0 or choice_index >= len(p.top2):
            raise ValueError("choice_index out of range")

        chosen = p.top2[choice_index]
        self._pending.pop(token, None)
        return {
            "source": "user_choice",
            "acronym": p.acronym,
            "meaning": chosen["meaning"],
            "confidence": chosen["confidence"],
        }

    def resolve_user_provided(self, token: str, fullForm: str, description: str = "") -> Dict[str, Any]:
        p = self._pending.get(token)
        if not p:
            raise KeyError("invalid pending token")

        self._pending.pop(token, None)
        return {
            "source": "user_provided",
            "acronym": p.acronym,
            "meaning": {"fullForm": fullForm, "description": description},
            "confidence": None,
        }


# Single canonical instance for the whole process. Every module (app.py's
# routes, agent.py) must import THIS object -- never instantiate
# HitlAcronymFlow() themselves.
hitl_flow = HitlAcronymFlow(timeout_seconds=settings.hitl_countdown_seconds)
