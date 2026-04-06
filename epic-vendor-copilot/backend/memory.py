"""
memory.py
---------
Conversation memory management for the Epic Vendor Services FAQ copilot.

Provides:
  - Turn: dataclass representing a single conversation turn
  - ConversationMemory: sliding-window memory using collections.deque
  - SessionStore: per-session memory manager with TTL-based eviction

No FastAPI imports — importable standalone.
"""

import heapq
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class Turn:
    """A single conversation turn (user or assistant)."""
    role: str                           # "user" or "assistant"
    content: str
    retrieved_ids: list[str] = field(default_factory=list)  # e.g. ["vs-1072"]
    turn_index: int = 0
    timestamp: float = field(default_factory=time.time)


class ConversationMemory:
    """
    Sliding-window conversation memory backed by a bounded deque.

    Keeps the most recent `max_turns` turns. Older turns are automatically
    evicted when new ones are added beyond capacity.
    """

    def __init__(self, max_turns: int = 6):
        self._turns: deque[Turn] = deque(maxlen=max_turns)

    def add(self, turn: Turn) -> None:
        """Append a turn to the memory window."""
        self._turns.append(turn)

    def context_window(self) -> list[Turn]:
        """Return all turns currently in memory, oldest first."""
        return list(self._turns)

    def used_faq_ids(self) -> set[str]:
        """Return the union of all retrieved_ids across every turn in memory."""
        ids: set[str] = set()
        for turn in self._turns:
            ids.update(turn.retrieved_ids)
        return ids

    def recency_context(self) -> list[dict]:
        """
        Build a recency-weighted context list.

        - Last 2 turns: full content  → {"role": str, "content": str}
        - Older turns: truncated      → {"role": str, "summary": content[:80]}
        """
        turns = list(self._turns)
        if not turns:
            return []

        result: list[dict] = []
        cutoff = max(0, len(turns) - 2)

        for i, turn in enumerate(turns):
            if i < cutoff:
                result.append({"role": turn.role, "summary": turn.content[:80]})
            else:
                result.append({"role": turn.role, "content": turn.content})

        return result

    def to_dict(self) -> dict:
        """Return a JSON-serializable snapshot of the memory state."""
        return {
            "turns": [
                {
                    "role": t.role,
                    "content": t.content,
                    "retrieved_ids": t.retrieved_ids,
                    "turn_index": t.turn_index,
                    "timestamp": t.timestamp,
                }
                for t in self._turns
            ],
            "total_turns": len(self._turns),
            "max_turns": self._turns.maxlen,
            "used_faq_ids": sorted(self.used_faq_ids()),
        }


class SessionStore:
    """
    Manages ConversationMemory instances keyed by session ID.

    Each session tracks its last-access time for TTL-based eviction.
    """

    def __init__(self):
        self._store: dict[str, tuple[ConversationMemory, float]] = {}
        self._heap: list[tuple[float, str]] = []

    def get_or_create(self, session_id: str) -> ConversationMemory:
        """Retrieve existing session memory or create a new one."""
        if session_id not in self._store:
            self._store[session_id] = (ConversationMemory(), time.time())
            heapq.heappush(self._heap, (time.time(), session_id))
        else:
            self.touch(session_id)
        return self._store[session_id][0]

    def touch(self, session_id: str) -> None:
        """Update the last-access timestamp for a session."""
        if session_id in self._store:
            mem = self._store[session_id][0]
            self._store[session_id] = (mem, time.time())

    def evict_stale(self, ttl_seconds: int = 1800) -> int:
        """
        Evict sessions not accessed within ttl_seconds.
        Uses a min-heap keyed on creation time for O(k log n) eviction
        where k = number of expired sessions, vs O(n) linear scan.
        At current scale (32 FAQ entries, small concurrent user count)
        this is equivalent, but documents the correct pattern for
        horizontal scaling where session counts grow to O(10^4+).
        """
        now = time.time()
        cutoff = now - ttl_seconds
        evicted = 0
        while self._heap and self._heap[0][0] < cutoff:
            _, sid = heapq.heappop(self._heap)
            if sid in self._store:
                _, last_access = self._store[sid]
                if last_access < cutoff:
                    del self._store[sid]
                    evicted += 1
                else:
                    # Session was touched after heap entry; re-push
                    heapq.heappush(self._heap, (last_access, sid))
        return evicted

    def remove(self, session_id: str) -> bool:
        """Remove a specific session. Returns True if it existed."""
        if session_id in self._store:
            del self._store[session_id]
            return True
        return False

    def active_count(self) -> int:
        """Return the number of currently active sessions."""
        return len(self._store)
