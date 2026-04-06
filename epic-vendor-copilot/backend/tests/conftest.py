"""
conftest.py
-----------
Shared pytest fixtures for backend tests.
"""

import sys
import pathlib

# Ensure the epic-vendor-copilot/ root is on sys.path so that
# `from backend.X import Y` resolves correctly when pytest is
# invoked from any directory.
_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import json
from pathlib import Path

import pytest

from backend.memory import ConversationMemory, SessionStore, Turn


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_queries() -> list[dict]:
    """Load the sample_queries.json fixture."""
    path = FIXTURES_DIR / "sample_queries.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.loads(f.read())


@pytest.fixture
def fresh_memory() -> ConversationMemory:
    """Return a fresh ConversationMemory with default max_turns=6."""
    return ConversationMemory(max_turns=6)


@pytest.fixture
def session_store() -> SessionStore:
    """Return a fresh SessionStore."""
    return SessionStore()


@pytest.fixture
def sample_turn() -> Turn:
    """Return a sample Turn for testing."""
    return Turn(
        role="user",
        content="What is Vendor Services?",
        retrieved_ids=["vs-1072"],
        turn_index=0,
        timestamp=1000.0,
    )
