"""
test_memory.py
--------------
Unit tests for backend.memory module.

Tests:
  - Deque evicts oldest turn when max_turns exceeded
  - used_faq_ids() unions IDs across all turns
  - recency_context() returns full content for last 2, summary for older
  - SessionStore.evict_stale() removes sessions beyond TTL

No FastAPI server needed.
"""

import time

import pytest

from backend.memory import ConversationMemory, SessionStore, Turn


class TestConversationMemoryEviction:
    """Test that the deque evicts the oldest turn when maxlen is exceeded."""

    def test_evicts_oldest_when_full(self, fresh_memory: ConversationMemory):
        """Adding a 7th turn to a max_turns=6 memory should evict the oldest."""
        turns = []
        for i in range(7):
            t = Turn(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Turn {i}",
                retrieved_ids=[f"vs-{i}"],
                turn_index=i,
                timestamp=1000.0 + i,
            )
            turns.append(t)
            fresh_memory.add(t)

        window = fresh_memory.context_window()
        assert len(window) == 6
        # Oldest turn (Turn 0) should be gone
        assert window[0].content == "Turn 1"
        assert window[-1].content == "Turn 6"

    def test_empty_memory_returns_empty_window(self):
        mem = ConversationMemory()
        assert mem.context_window() == []

    def test_single_turn_stays(self):
        mem = ConversationMemory(max_turns=6)
        t = Turn(role="user", content="Hello", turn_index=0)
        mem.add(t)
        assert len(mem.context_window()) == 1
        assert mem.context_window()[0].content == "Hello"


class TestUsedFaqIds:
    """Test that used_faq_ids() correctly unions IDs across all turns."""

    def test_unions_across_turns(self, fresh_memory: ConversationMemory):
        fresh_memory.add(Turn(role="user", content="Q1", retrieved_ids=["vs-1", "vs-2"], turn_index=0))
        fresh_memory.add(Turn(role="assistant", content="A1", retrieved_ids=["vs-2", "vs-3"], turn_index=1))
        fresh_memory.add(Turn(role="user", content="Q2", retrieved_ids=["vs-4"], turn_index=2))

        ids = fresh_memory.used_faq_ids()
        assert ids == {"vs-1", "vs-2", "vs-3", "vs-4"}

    def test_empty_memory_returns_empty_set(self):
        mem = ConversationMemory()
        assert mem.used_faq_ids() == set()

    def test_no_retrieved_ids(self, fresh_memory: ConversationMemory):
        fresh_memory.add(Turn(role="user", content="Q1", retrieved_ids=[], turn_index=0))
        assert fresh_memory.used_faq_ids() == set()


class TestRecencyContext:
    """Test recency_context() returns full content for last 2 turns, summary for older."""

    def test_full_and_summary_split(self, fresh_memory: ConversationMemory):
        for i in range(5):
            fresh_memory.add(Turn(
                role="user" if i % 2 == 0 else "assistant",
                content=f"This is turn number {i} with some extra content that goes beyond eighty characters for truncation testing purposes.",
                turn_index=i,
            ))

        ctx = fresh_memory.recency_context()
        assert len(ctx) == 5

        # First 3 turns should have "summary" (truncated to 80 chars)
        for i in range(3):
            assert "summary" in ctx[i]
            assert "content" not in ctx[i]
            assert len(ctx[i]["summary"]) <= 80

        # Last 2 turns should have full "content"
        for i in range(3, 5):
            assert "content" in ctx[i]
            assert "summary" not in ctx[i]

    def test_two_or_fewer_turns_all_full(self):
        mem = ConversationMemory()
        mem.add(Turn(role="user", content="Hello", turn_index=0))
        mem.add(Turn(role="assistant", content="World", turn_index=1))

        ctx = mem.recency_context()
        assert len(ctx) == 2
        assert all("content" in c for c in ctx)
        assert all("summary" not in c for c in ctx)

    def test_empty_recency_context(self):
        mem = ConversationMemory()
        assert mem.recency_context() == []


class TestSessionStoreEviction:
    """Test SessionStore.evict_stale() removes sessions older than TTL."""

    def test_evict_stale_removes_old_sessions(self, session_store: SessionStore):
        # Create a session and manually backdate its timestamp
        mem = session_store.get_or_create("old-session")
        old_time = time.time() - 3600
        session_store._store["old-session"] = (mem, old_time)
        # Also backdate the heap entry so heap-based eviction sees it
        session_store._heap = [(old_time, "old-session")]

        # Create a fresh session
        session_store.get_or_create("new-session")

        evicted = session_store.evict_stale(ttl_seconds=1800)
        assert evicted == 1
        assert "old-session" not in session_store._store
        assert "new-session" in session_store._store

    def test_no_eviction_when_all_fresh(self, session_store: SessionStore):
        session_store.get_or_create("session-a")
        session_store.get_or_create("session-b")
        evicted = session_store.evict_stale(ttl_seconds=1800)
        assert evicted == 0

    def test_get_or_create_returns_same_memory(self, session_store: SessionStore):
        mem1 = session_store.get_or_create("test-id")
        mem2 = session_store.get_or_create("test-id")
        assert mem1 is mem2

    def test_touch_updates_timestamp(self, session_store: SessionStore):
        session_store.get_or_create("touch-test")
        # Backdate
        mem = session_store._store["touch-test"][0]
        session_store._store["touch-test"] = (mem, time.time() - 3600)
        # Touch should update
        session_store.touch("touch-test")
        _, ts = session_store._store["touch-test"]
        assert time.time() - ts < 5  # Should be recent


class TestToDict:
    """Test that to_dict() returns a JSON-serializable snapshot."""

    def test_to_dict_structure(self, fresh_memory: ConversationMemory):
        fresh_memory.add(Turn(role="user", content="Hello", retrieved_ids=["vs-1"], turn_index=0, timestamp=1000.0))
        d = fresh_memory.to_dict()

        assert "turns" in d
        assert "total_turns" in d
        assert "max_turns" in d
        assert "used_faq_ids" in d
        assert d["total_turns"] == 1
        assert d["max_turns"] == 6
        assert d["used_faq_ids"] == ["vs-1"]
        assert d["turns"][0]["role"] == "user"
        assert d["turns"][0]["content"] == "Hello"


class TestHeapEviction:
    """Test min-heap based eviction in SessionStore."""

    def test_heap_eviction_removes_expired_sessions(self):
        store = SessionStore()
        store.get_or_create("s1")
        store.get_or_create("s2")
        store.get_or_create("s3")
        # Manually backdate all sessions in both _store and _heap
        old_time = time.time() - 3600
        for sid in ["s1", "s2", "s3"]:
            mem = store._store[sid][0]
            store._store[sid] = (mem, old_time)
        import heapq
        store._heap = []
        for sid in ["s1", "s2", "s3"]:
            heapq.heappush(store._heap, (old_time, sid))
        evicted = store.evict_stale(1800)
        assert evicted == 3
        assert store.active_count() == 0

    def test_heap_does_not_evict_fresh_sessions(self):
        store = SessionStore()
        store.get_or_create("fresh1")
        store.get_or_create("fresh2")
        evicted = store.evict_stale(1800)
        assert evicted == 0
        assert store.active_count() == 2
