"""
memory.py
Phase 6 (Planning, Memory & Context): short-term conversation memory
(mirrors langchain.memory.ConversationBufferWindowMemory) plus a small
session-scoped "known facts" slot (e.g. vehicle registration number once
given) so the agent doesn't re-ask for it every turn.

Design choice: memory is PER-SESSION and in-process only. It is reset when
the session ends and is never written to the persistent interaction log in
raw form (see monitoring/langfuse_logger.py, which logs PII-redacted
summaries only). This satisfies "Must not store personal data in logs"
while still allowing natural multi-turn conversation.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional

WINDOW_SIZE = 6  # keep last N turns


@dataclass
class Turn:
    role: str   # "user" | "agent"
    text: str


@dataclass
class SessionMemory:
    session_id: str
    turns: List[Turn] = field(default_factory=list)
    known_facts: Dict[str, str] = field(default_factory=dict)   # e.g. {"vehicle_reg": "MH12AB1234"}
    preferences: Dict[str, str] = field(default_factory=dict)   # e.g. {"response_length": "concise"}
    complaint_topics: List[str] = field(default_factory=list)   # for repeated-complaint detection

    def add_turn(self, role: str, text: str):
        self.turns.append(Turn(role=role, text=text))
        self.turns = self.turns[-WINDOW_SIZE:]

    def set_fact(self, key: str, value: str):
        self.known_facts[key] = value

    def get_fact(self, key: str) -> Optional[str]:
        return self.known_facts.get(key)

    def as_prompt_context(self) -> str:
        if not self.turns:
            return "(no earlier turns in this session)"
        lines = [f"{t.role}: {t.text}" for t in self.turns]
        return "\n".join(lines)

    def note_complaint(self, topic: str) -> bool:
        """Returns True if this is a REPEATED complaint about the same topic
        (i.e. topic already logged once this session)."""
        is_repeat = topic in self.complaint_topics
        self.complaint_topics.append(topic)
        return is_repeat


class MemoryStore:
    """Holds one SessionMemory per active session_id."""

    def __init__(self):
        self._sessions: Dict[str, SessionMemory] = {}

    def get(self, session_id: str) -> SessionMemory:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMemory(session_id=session_id)
        return self._sessions[session_id]

    def reset(self, session_id: str):
        self._sessions.pop(session_id, None)
