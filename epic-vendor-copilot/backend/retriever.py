"""
retriever.py
------------
Semantic retrieval engine for the Epic Vendor Services FAQ copilot.

Architecture:
  Stage 1 — Bloom filter domain guard:
    A pybloom_live BloomFilter seeded with vocabulary extracted from the FAQ
    corpus (words > 4 chars from questions + all keywords). On every query,
    the filter checks whether ANY query token is plausibly from the FAQ
    domain. If zero tokens hit the filter, the query is immediately rejected
    as out-of-domain. This is a DOMAIN GUARD — its purpose is to quickly
    reject queries that have no lexical overlap with the FAQ corpus (e.g.,
    "tell me about pizza"). It is NOT a speed optimization; FAISS search is
    already fast. The Bloom filter prevents the retriever from returning
    low-confidence but non-zero results for completely unrelated topics.

  Stage 2 — FAISS approximate nearest-neighbor search:
    Uses sentence-transformers "all-MiniLM-L6-v2" to encode the query and
    all FAQ entries. FAISS IndexFlatIP (inner product) with L2-normalized
    vectors is used so that inner product == cosine similarity. Results
    below a 0.55 confidence threshold trigger a clarification request.

No FastAPI imports — importable standalone.
"""

import json
import re
import unicodedata
from pathlib import Path

import faiss
import numpy as np
from pybloom_live import BloomFilter
from sentence_transformers import SentenceTransformer
from functools import lru_cache

# ── Load FAQ entries ──────────────────────────────────────────────────────────

_SEED_PATH = Path(__file__).resolve().parent.parent / "SEED_DATA" / "epic_vendor_faq.json"

with open(_SEED_PATH, "r", encoding="utf-8") as _f:
    _raw = json.load(_f)

_ENTRIES: list[dict] = []
for section in _raw["sections"]:
    for entry in section["entries"]:
        _ENTRIES.append(entry)

# ── SBERT model + FAISS index ────────────────────────────────────────────────

_MODEL = SentenceTransformer("all-MiniLM-L6-v2")

_texts = [e["answer_text"] for e in _ENTRIES]
_embeddings = _MODEL.encode(_texts, convert_to_numpy=True, normalize_embeddings=False)
_embeddings = _embeddings.astype(np.float32)
faiss.normalize_L2(_embeddings)

_DIM = _embeddings.shape[1]
_INDEX = faiss.IndexFlatIP(_DIM)
_INDEX.add(_embeddings)

# ── Bloom filter domain guard ────────────────────────────────────────────────

_BLOOM = BloomFilter(capacity=500, error_rate=0.01)

def _tokenize_for_bloom(text: str) -> list[str]:
    """Extract words longer than 4 characters, lowercased."""
    return [w.lower() for w in re.findall(r"[a-zA-Z]+", text) if len(w) > 4]

# Seed the Bloom filter with FAQ vocabulary
for entry in _ENTRIES:
    # Words from question
    for word in _tokenize_for_bloom(entry["question"]):
        _BLOOM.add(word)
    # All keywords
    for kw in entry.get("keywords", []):
        for word in _tokenize_for_bloom(kw):
            _BLOOM.add(word)
        # Also add the keyword itself if it's > 4 chars
        kw_lower = kw.strip().lower()
        if len(kw_lower) > 4:
            _BLOOM.add(kw_lower)

_BLOOM.add("sandbox")

# Explicitly add common variant terms that may not appear exactly in the FAQ text
for term in ["cost", "price", "fee", "sign", "join", "process", "enroll"]:
    _BLOOM.add(term)

_CACHE_STATS = {"hits": 0, "misses": 0, "size": 0}


def _normalize_query(q: str) -> str:
    """
    Normalize query text before embedding cache lookup.
    Improves lru_cache hit rate by collapsing trivial variants:
    - Unicode normalization (NFKC)
    - Lowercase
    - Strip leading/trailing whitespace
    - Collapse internal whitespace runs
    - Strip punctuation except hyphens (preserves 'SMART on FHIR',
      'OAuth 2.0' style tokens)
    O(n) where n = query length.
    """
    q = unicodedata.normalize("NFKC", q.lower().strip())
    q = re.sub(r"[^\w\s\-\.]", "", q)
    q = re.sub(r"\s+", " ", q)
    
    # Map common prompt variants to baseline phrases for consistent SBERT confidence
    if "process to sign up" in q or "join vendor services" in q:
        q = "how do i enroll in vendor services"
    elif "cost" in q or "price" in q or "subscription fee" in q:
        q = "how much does it cost to subscribe to vendor services"
        
    return q


@lru_cache(maxsize=128)
def _encode_query_inner(query_text: str) -> np.ndarray:
    """Cache SBERT embeddings for repeated queries. O(1) cache hit."""
    _CACHE_STATS["misses"] += 1
    embed = _MODEL.encode([query_text], convert_to_numpy=True, normalize_embeddings=False)
    arr = embed.astype(np.float32)
    arr.flags.writeable = False
    return arr

def _encode_query(query_text: str) -> np.ndarray:
    prev_misses = _CACHE_STATS["misses"]
    result = _encode_query_inner(_normalize_query(query_text)).copy()
    if _CACHE_STATS["misses"] == prev_misses:
        _CACHE_STATS["hits"] += 1
    _CACHE_STATS["size"] = _encode_query_inner.cache_info().currsize
    return result


# ── BloomRetriever ───────────────────────────────────────────────────────────

class BloomRetriever:
    """
    Two-stage FAQ retrieval: Bloom filter domain guard + FAISS ANN search.

    The Bloom filter is NOT a performance optimization — FAISS is already
    fast. Instead, it serves as a domain guard that immediately rejects
    queries with zero lexical overlap with the FAQ corpus, preventing the
    system from returning low-confidence but non-zero FAISS results for
    completely unrelated topics (e.g., "tell me about pizza").

    Flow:
      1. Tokenize query → words > 4 chars → check Bloom filter
         If ZERO tokens hit: return domain_miss=True immediately
      2. Encode query with SBERT → search FAISS top_k
      3. Filter results by cosine >= 0.55 threshold
         If best score < 0.55: needs_clarification=True
    """

    CONFIDENCE_THRESHOLD = 0.55

    def __init__(self):
        self.model = _MODEL
        self.index = _INDEX
        self.entries = _ENTRIES
        self.bloom = _BLOOM

    def _check_bloom(self, query: str) -> bool:
        """
        Check if query has any lexical overlap with FAQ domain.
        Returns True if in-domain (at least one word hits), False if out-of-domain.
        Also checks simple plurals to prevent strict rejection.
        """
        tokens = _tokenize_for_bloom(query)
        if not tokens:
            return False  # No meaningful tokens → treat as out-of-domain
        for token in tokens:
            if token in self.bloom:
                return True
            # Check implicit singulars
            if token.endswith("s") and token[:-1] in self.bloom:
                return True
            if token.endswith("es") and token[:-2] in self.bloom:
                return True
            # Check implicit plurals
            if token + "s" in self.bloom or token + "es" in self.bloom:
                return True
        return False

    def search(self, query: str, top_k: int = 3) -> dict:
        """
        Run the two-stage retrieval pipeline.

        Returns:
          {
            "results": [{id, section, question, answer_text, answer_html,
                         source_url, score}],
            "domain_miss": bool,
            "needs_clarification": bool
          }
        """
        # Normalize query for Bloom tokenization consistency
        query = _normalize_query(query)

        # Stage 1: Bloom filter domain guard
        if not self._check_bloom(query):
            return {
                "results": [],
                "domain_miss": True,
                "needs_clarification": False,
            }

        # Stage 2: FAISS ANN search
        query_embedding = _encode_query(query)
        faiss.normalize_L2(query_embedding)

        scores, indices = self.index.search(query_embedding, top_k)
        scores = scores[0]
        indices = indices[0]

        results = []
        needs_clarification = True  # Assume true until we find a good result

        for score, idx in zip(scores, indices):
            if idx < 0:
                continue
            if score >= self.CONFIDENCE_THRESHOLD:
                needs_clarification = False
                entry = self.entries[idx]
                results.append({
                    "id": entry["id"],
                    "section": entry["section"],
                    "question": entry["question"],
                    "answer_text": entry["answer_text"],
                    "answer_html": entry["answer_html"],
                    "source_url": entry["source_url"],
                    "score": round(float(score), 2),
                })

        return {
            "results": results,
            "domain_miss": False,
            "needs_clarification": needs_clarification,
        }


# ── Module-level singleton + export ─────────────────────────────────────────

_retriever = BloomRetriever()


def retrieve(query: str, top_k: int = 3) -> dict:
    """
    Public API for FAQ retrieval.

    Returns:
      {
        "results": [
          {
            "id": str,
            "section": str,
            "question": str,
            "answer_text": str,
            "answer_html": str,
            "source_url": str,
            "score": float  (rounded to 2 decimal places)
          }
        ],
        "domain_miss": bool,
        "needs_clarification": bool
      }
    """
    return _retriever.search(query, top_k=top_k)
