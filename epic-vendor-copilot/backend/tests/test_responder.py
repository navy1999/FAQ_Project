"""
test_responder.py
-----------------
Unit tests for backend.responder module.

Tests:
  - MODE_A returns non-empty answer for valid retrieval result
  - MODE_A returns clarification string when needs_clarification=True
  - build_prompt never exceeds 800 tokens regardless of input size
  - All tests run with OPENAI_API_KEY unset (template mode)
"""

import os

import pytest

# Ensure tests run in template mode
os.environ.pop("OPENAI_API_KEY", None)

from backend.responder import (
    MODE,
    _CLARIFICATION_RESPONSE,
    _TOKEN_BUDGET,
    _count_tokens,
    build_prompt,
    synthesize,
)
from backend.memory import ConversationMemory, Turn


class TestModeAValidResult:
    """MODE_A should return non-empty answer for valid retrieval results."""

    def test_single_result(self):
        retrieval = {
            "results": [
                {
                    "id": "vs-1072",
                    "section": "General",
                    "question": "What is Vendor Services?",
                    "answer_text": "Vendor Services is a support program offered by Epic.",
                    "answer_html": "<p>Vendor Services is a support program.</p>",
                    "source_url": "https://vendorservices.epic.com/FAQ/Index",
                    "score": 0.92,
                }
            ],
            "domain_miss": False,
            "needs_clarification": False,
        }
        result = synthesize("what is vendor services", retrieval)
        assert result["answer"]
        assert len(result["answer"]) > 0
        assert result["mode"] == "template"
        assert result["clarification_needed"] is False
        assert "vs-1072" in result["source_ids"]

    def test_multiple_results(self):
        retrieval = {
            "results": [
                {
                    "id": "vs-1072",
                    "section": "General",
                    "question": "What is Vendor Services?",
                    "answer_text": "Vendor Services is a support program.",
                    "answer_html": "",
                    "source_url": "https://vendorservices.epic.com/FAQ/Index",
                    "score": 0.92,
                },
                {
                    "id": "vs-1073",
                    "section": "General",
                    "question": "Who uses Vendor Services?",
                    "answer_text": "Developers enrolled in Vendor Services.",
                    "answer_html": "",
                    "source_url": "https://vendorservices.epic.com/FAQ/Index",
                    "score": 0.85,
                },
            ],
            "domain_miss": False,
            "needs_clarification": False,
        }
        result = synthesize("tell me about vendor services", retrieval)
        assert result["answer"]
        assert "1." in result["answer"]  # Numbered list
        assert result["mode"] == "template"


class TestModeAClarification:
    """MODE_A should return clarification string for edge cases."""

    def test_needs_clarification(self):
        retrieval = {
            "results": [],
            "domain_miss": False,
            "needs_clarification": True,
        }
        result = synthesize("something vague", retrieval)
        assert result["answer"] == _CLARIFICATION_RESPONSE
        assert result["clarification_needed"] is True

    def test_domain_miss(self):
        retrieval = {
            "results": [],
            "domain_miss": True,
            "needs_clarification": False,
        }
        result = synthesize("tell me about pizza", retrieval)
        assert result["answer"] == _CLARIFICATION_RESPONSE
        assert result["clarification_needed"] is True


class TestBuildPromptTokenBudget:
    """build_prompt should never exceed 800 tokens regardless of input."""

    def test_within_budget_normal(self):
        chunks = [
            {"answer_text": "Short answer about vendor services."},
        ]
        prompt = build_prompt("what is vendor services", chunks, [])
        assert _count_tokens(prompt) <= _TOKEN_BUDGET

    def test_within_budget_large_memory(self):
        """Even with many long memory turns, prompt stays within budget."""
        # Create artificially large memory context
        memory_context = []
        for i in range(20):
            memory_context.append({
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"This is a very long turn number {i} " + "word " * 100,
            })

        chunks = [
            {"answer_text": "A " * 200},
            {"answer_text": "B " * 200},
            {"answer_text": "C " * 200},
        ]

        prompt = build_prompt(
            "what is vendor services with a really long question " * 5,
            chunks,
            memory_context,
        )
        assert _count_tokens(prompt) <= _TOKEN_BUDGET

    def test_within_budget_extreme(self):
        """Extreme case: huge everything."""
        memory_context = [
            {"role": "user", "content": "word " * 500}
            for _ in range(10)
        ]
        chunks = [
            {"answer_text": "answer " * 500}
            for _ in range(3)
        ]
        prompt = build_prompt("question " * 100, chunks, memory_context)
        assert _count_tokens(prompt) <= _TOKEN_BUDGET


class TestTokenCounter:
    """Verify _count_tokens uses whitespace splitting."""

    def test_basic_count(self):
        assert _count_tokens("hello world") == 2

    def test_empty_string(self):
        assert _count_tokens("") == 0

    def test_multiline(self):
        assert _count_tokens("hello\nworld\nfoo") == 3


class TestSynthesizeWithMemory:
    """Test synthesize works correctly with ConversationMemory."""

    def test_with_memory_object(self):
        mem = ConversationMemory()
        mem.add(Turn(role="user", content="previous question", turn_index=0))
        mem.add(Turn(role="assistant", content="previous answer", turn_index=1))

        retrieval = {
            "results": [
                {
                    "id": "vs-1072",
                    "section": "General",
                    "question": "What is Vendor Services?",
                    "answer_text": "Vendor Services is a support program.",
                    "answer_html": "",
                    "source_url": "https://vendorservices.epic.com/FAQ/Index",
                    "score": 0.92,
                }
            ],
            "domain_miss": False,
            "needs_clarification": False,
        }
        result = synthesize("what is vendor services", retrieval, memory=mem)
        assert result["answer"]
        assert result["mode"] == "template"
