"""
test_retriever.py
-----------------
Unit tests for backend.retriever module.

Tests:
  - Known FAQ question returns high top_score (>= 0.72)
  - Off-topic query returns low top_score (< 0.45)
  - Broad query returns reasonable top_score (0.45 <= score < 0.72)
  - Results are sorted by score descending

All tests import retriever directly, no server needed.
"""

import pytest
from backend.retriever import retrieve


class TestKnownFAQQuery:
    """Known FAQ questions should return results with high confidence."""

    def test_what_is_vendor_services(self):
        result = retrieve("what is vendor services")
        assert result["top_score"] is not None
        assert result["top_score"] >= 0.72
        assert len(result["results"]) > 0

    def test_returns_expected_fields(self):
        result = retrieve("what is vendor services")
        assert "results" in result
        assert "top_score" in result
        
        first = result["results"][0]
        assert "id" in first
        assert "section" in first
        assert "question" in first
        assert "answer_text" in first
        assert "source_url" in first
        assert "score" in first


class TestScoreClassification:
    """Tests for semantic score classification based on new thresholds."""

    def test_off_domain_low_score(self):
        """Off-topic queries should return low scores."""
        result = retrieve("what is the capital of France")
        # May return results, but top_score should be very low
        assert result["top_score"] is None or result["top_score"] < 0.45

    def test_pizza_low_score(self):
        result = retrieve("tell me about pizza")
        assert result["top_score"] is None or result["top_score"] < 0.45

    def test_vague_query_mid_score(self):
        """A vague query like 'technical issues' should return a mid-range score."""
        result = retrieve("technical issues")
        # 'technical issues' is related but vague. 
        # We expect it to be in the clarification range [0.45, 0.72)
        assert result["top_score"] is not None
        assert 0.45 <= result["top_score"] < 0.72


class TestRetrieverLogic:
    """General retriever functionality tests."""

    def test_top_k_ordering(self):
        """results are sorted by score descending"""
        res = retrieve("what is vendor services and what are APIs?", top_k=3)
        results = res.get("results", [])
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i]["score"] >= results[i+1]["score"]

    def test_known_query_hit_id(self):
        """'what is vendor services' returns vs-1072 as top result"""
        res = retrieve("what is vendor services")
        assert len(res["results"]) > 0
        assert res["results"][0]["id"] == "vs-1072"

    def test_multi_result_count(self):
        """a broad query returns up to 3 results"""
        res = retrieve("enrollment", top_k=3)
        assert 1 <= len(res["results"]) <= 3


class TestNormalization:
    """Tests for query normalization and caching."""

    def test_normalize_query_logic(self):
        from backend.retriever import _normalize_query
        result = _normalize_query("  How  do I  LOG IN?  ")
        assert result == "how do i log in"

    def test_cache_hit_after_normalization(self):
        from backend.retriever import _CACHE_STATS, _encode_query_inner
        _encode_query_inner.cache_clear()
        _CACHE_STATS["hits"] = 0
        _CACHE_STATS["misses"] = 0
        
        retrieve("How do I enroll?")
        hits_before = _CACHE_STATS["hits"]
        
        retrieve("how do i enroll")
        assert _CACHE_STATS["hits"] > hits_before


class TestQueryVariants:
    """Test that various query phrasings for the same FAQ topic produce confident hits."""

    def test_enrollment_variants(self):
        variants = [
            "How do I enroll in Vendor Services?",
            "how do i enroll in vendor services",
            "HOW DO I ENROLL IN VENDOR SERVICES?",
            "  How do I enroll in Vendor Services?  ",
            "What is the process to sign up?",
            "I want to join Vendor Services"
        ]
        for v in variants:
            res = retrieve(v)
            assert res["top_score"] >= 0.72, f"Variant failed: {v} (score: {res['top_score']})"

    def test_cost_variants(self):
        variants = [
            "How much does it cost?",
            "What is the price?",
            "What is the subscription fee?"
        ]
        for v in variants:
            res = retrieve(v)
            assert res["top_score"] >= 0.72, f"Variant failed: {v} (score: {res['top_score']})"
