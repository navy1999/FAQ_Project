"""
test_retriever.py
-----------------
Unit tests for backend.retriever module.

Tests:
  - Known FAQ question returns score >= 0.55
  - Off-domain query returns domain_miss=True
  - Paraphrased enrollment query is NOT Bloom-rejected
  - Vague partial query returns needs_clarification=True

All tests import retriever directly, no server needed.
"""

import pytest

from backend.retriever import retrieve


class TestKnownFAQQuery:
    """Known FAQ questions should return results with good confidence."""

    def test_what_is_vendor_services(self):
        result = retrieve("what is vendor services")
        assert not result["domain_miss"]
        assert len(result["results"]) > 0
        assert result["results"][0]["score"] >= 0.55

    def test_returns_expected_fields(self):
        result = retrieve("what is vendor services")
        first = result["results"][0]
        assert "id" in first
        assert "section" in first
        assert "question" in first
        assert "answer_text" in first
        assert "answer_html" in first
        assert "source_url" in first
        assert "score" in first


class TestDomainMiss:
    """Completely off-domain queries should be caught by the Bloom filter."""

    def test_off_domain_returns_domain_miss(self):
        result = retrieve("what is the capital of France")
        assert result["domain_miss"] is True
        assert result["results"] == []

    def test_pizza_is_off_domain(self):
        result = retrieve("tell me about pizza")
        assert result["domain_miss"] is True


class TestParaphrasedQuery:
    """Paraphrased enrollment queries should NOT be Bloom-rejected."""

    def test_how_do_i_join_reaches_faiss(self):
        """
        A paraphrased enrollment query that contains FAQ vocabulary words
        should NOT be Bloom-rejected. 'register' is a known FAQ keyword,
        so 'how do I register' should reach the FAISS stage.
        """
        result = retrieve("how do I register to enroll")
        # The key assertion is that Bloom didn't reject it
        # (it reaches FAISS stage). Score may or may not pass threshold.
        assert result["domain_miss"] is False


class TestClarificationNeeded:
    """Vague queries below confidence threshold should flag clarification."""

    def test_vague_query_needs_clarification(self):
        """
        A very vague partial query like 'thing' should either be
        domain_miss (Bloom rejection) or needs_clarification (low FAISS scores).
        """
        result = retrieve("thing")
        # Either Bloom rejects it or FAISS returns low scores
        assert result["domain_miss"] is True or result["needs_clarification"] is True

    def test_ambiguous_single_word(self):
        """A single ambiguous word should not return confident results."""
        result = retrieve("stuff about things")
        assert result["domain_miss"] is True or result["needs_clarification"] is True

class TestPluralization:
    """Test morphological variants (e.g., plurals) correctly bypass the Bloom Filter."""

    def test_plural_vendors(self):
        """'vendors' should hit 'vendor' and pass the Bloom check."""
        result = retrieve("vendors")
        # Should not be a domain_miss! It might need clarification depending on score, but PyBloom passes.
        assert result["domain_miss"] is False
