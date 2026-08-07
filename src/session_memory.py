import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class SessionMemory:
    last_activity: float
    # Store turns so we can produce “last 5 summaries + last one message”
    turns: List[Tuple[str, str]] = field(default_factory=list)  # (user, assistant)

    def remember(self, user_msg: str, assistant_msg: str) -> None:
        self.turns.append((user_msg or "", assistant_msg or ""))
        # Cap turns to keep memory small; summaries are derived anyway.
        if len(self.turns) > 50:
            self.turns = self.turns[-50:]

    def build_memory_text(self) -> str:
        """Return cached memory text.

        Requirement:
          - last 5 messages summaries
          - last one message combine with the summary and provided as history context

        Since we are keeping “memory in cache” (cleared on app close), we use a lightweight
        deterministic summary instead of an LLM summarizer:
          - summary_i: one-line paraphrase = assistant answer trimmed
          - last_one_message: latest user question trimmed
        """
        if not self.turns:
            return ""

        # last one message = latest user question
        last_user, last_assistant = self.turns[-1]

        # last 5 summaries = summaries for up to previous 5 turns (including latest assistant answer is fine
        # but we keep them for turns ending before the last user to match wording)
        prev = self.turns[:-1]
        prev_summaries = prev[-5:]

        lines: List[str] = []
        for i, (u, a) in enumerate(prev_summaries, 1):
            a_trim = (a or "").strip()
            if len(a_trim) > 220:
                a_trim = a_trim[:220].rstrip() + "..."
            u_trim = (u or "").strip()
            if len(u_trim) > 120:
                u_trim = u_trim[:120].rstrip() + "..."
            lines.append(f"Summary{i}: Asked '{u_trim}' -> Answer: {a_trim}")

        # combine with last user message
        last_u_trim = (last_user or "").strip()
        if len(last_u_trim) > 160:
            last_u_trim = last_u_trim[:160].rstrip() + "..."

        # also include last assistant briefly to help follow-up queries
        last_a_trim = (last_assistant or "").strip()
        if len(last_a_trim) > 220:
            last_a_trim = last_a_trim[:220].rstrip() + "..."

        lines.append(f"LastUser: {last_u_trim}")
        if last_a_trim:
            lines.append(f"LastAnswer: {last_a_trim}")

        return "\n".join(lines).strip()


class SessionMemoryStore:
    def __init__(self, ttl_seconds: int = 1800):
        self.ttl_seconds = ttl_seconds
        self._sessions: Dict[str, SessionMemory] = {}

    def _expired(self, s: SessionMemory) -> bool:
        return (time.time() - s.last_activity) > self.ttl_seconds

    def get(self, session_id: str, create: bool = True) -> Optional[SessionMemory]:
        if not session_id:
            return None
        s = self._sessions.get(session_id)
        if s is None:
            if not create:
                return None
            s = SessionMemory(last_activity=time.time())
            self._sessions[session_id] = s
            return s

        if self._expired(s):
            # clear session if expired
            self._sessions.pop(session_id, None)
            if not create:
                return None
            s = SessionMemory(last_activity=time.time())
            self._sessions[session_id] = s
            return s

        s.last_activity = time.time()
        return s

    def update_activity(self, session_id: str) -> None:
        s = self._sessions.get(session_id)
        if s is not None:
            s.last_activity = time.time()

    def clear_all(self) -> None:
        self._sessions.clear()
