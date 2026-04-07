"""
retriever.py
------------
Semantic retrieval engine for the Epic Vendor Services FAQ copilot.

Architecture:
  FAISS approximate nearest-neighbor search:
    Uses sentence-transformers "multi-qa-MiniLM-L6-cos-v1" to encode the query
    and all FAQ entries. FAISS IndexFlatIP (inner product) with L2-normalized
    vectors gives cosine similarity scores in [0, 1].

Confidence thresholds (mirrors main.py routing logic):
  score < 0.45          -> domain_miss  (out-of-domain or completely unrelated)
  0.45 <= score < 0.72  -> needs_clarification (in-domain but ambiguous)
  score >= 0.72         -> confident answer

These flags are returned directly on every retrieve() call so that
diagnose.py and run_query_tests.py can read routing decisions without
reimplementing the threshold logic.
"""

import json
import re
import unicodedata
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from functools import lru_cache

import nltk
from nltk.corpus import wordnet as _wordnet


# ── Threshold constants ───────────────────────────────────────────────────────

SCORE_DOMAIN_MISS   = 0.45   # below this -> domain miss
SCORE_CLARIFICATION = 0.72   # below this (but >= DOMAIN_MISS) -> clarification


def _get_wordnet_synonyms(term: str) -> list[str]:
    """
    Return up to 5 WordNet lemma synonyms for a single-word term.
    Multi-word terms (e.g. 'sign up') are skipped — WordNet covers
    single words only reliably.
    """
    if " " in term.strip():
        return []
    syns: set[str] = set()
    for synset in _wordnet.synsets(term):
        for lemma in synset.lemmas():
            s = lemma.name().replace("_", " ").lower()
            if s != term.lower() and len(s) > 2:
                syns.add(s)
        if len(syns) >= 5:
            break
    return list(syns)[:5]


# ── Load FAQ entries ──────────────────────────────────────────────────────────

_SEED_PATH = Path(__file__).resolve().parent.parent / "SEED_DATA" / "epic_vendor_faq.json"

with open(_SEED_PATH, "r", encoding="utf-8") as _f:
    _raw = json.load(_f)

_ENTRIES: list[dict] = []
for section in _raw["sections"]:
    for entry in section["entries"]:
        _ENTRIES.append(entry)


# ── SBERT model + FAISS index ────────────────────────────────────────────────

_MODEL = SentenceTransformer("multi-qa-MiniLM-L6-cos-v1")

_texts: list[str] = []
_entry_index_map: list[int] = []   # FAISS position -> _ENTRIES index

for _i, _e in enumerate(_ENTRIES):
    _texts.append(_e["question"])
    _entry_index_map.append(_i)

    for _field in ("keywords", "synonyms"):
        for _term in (_e.get(_field) or []):
            _term = _term.strip()
            if not _term:
                continue
            _texts.append(_term)
            _entry_index_map.append(_i)
            for _syn in _get_wordnet_synonyms(_term):
                _texts.append(_syn)
                _entry_index_map.append(_i)

_embeddings = _MODEL.encode(_texts, convert_to_numpy=True, normalize_embeddings=False)
_embeddings = _embeddings.astype(np.float32)
faiss.normalize_L2(_embeddings)

_DIM = _embeddings.shape[1]
_INDEX = faiss.IndexFlatIP(_DIM)
_INDEX.add(_embeddings)
_CACHE_STATS = {"hits": 0, "misses": 0, "size": 0}


def _normalize_query(q: str) -> str:
    """
    Normalize query text before embedding cache lookup.
    Improves lru_cache hit rate by collapsing trivial variants.
    """
    q = unicodedata.normalize("NFKC", q.lower().strip())
    q = re.sub(r"[^\w\s\-\.]", "", q)
    q = re.sub(r"\s+", " ", q)
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


# ── FAQ Retriever ─────────────────────────────────────────────────────────────

class FAQRetriever:
    """
    Semantic FAQ retrieval using FAISS ANN search.
    """

    def __init__(self):
        self.model = _MODEL
        self.index = _INDEX
        self.entries = _ENTRIES
        self.entry_index_map = _entry_index_map

    def search(self, query: str, top_k: int = 3) -> dict:
        """
        Run the FAISS ANN search pipeline.

        Returns
        -------
        {
          "results":              list of matched FAQ dicts with score,
          "top_score":            float | None,
          "domain_miss":          bool  (top_score < SCORE_DOMAIN_MISS),
          "needs_clarification":  bool  (SCORE_DOMAIN_MISS <= top_score < SCORE_CLARIFICATION)
        }
        """
        query = _normalize_query(query)
        query_embedding = _encode_query(query)
        faiss.normalize_L2(query_embedding)

        scores, indices = self.index.search(query_embedding, top_k)
        scores = scores[0]
        indices = indices[0]

        results = []
        top_score = None

        for i, (score, idx) in enumerate(zip(scores, indices)):
            if idx < 0:
                continue

            s = round(float(score), 4)
            if i == 0:
                top_score = s

            entry = self.entries[self.entry_index_map[idx]]
            results.append({
                "id":          entry["id"],
                "section":     entry["section"],
                "question":    entry["question"],
                "answer_text": entry["answer_text"],
                "source_url":  entry["source_url"],
                "score":       s,
            })

        seen_ids = {}
        for r in results:
            eid = r["id"]
            if eid not in seen_ids or r["score"] > seen_ids[eid]["score"]:
                seen_ids[eid] = r
        results = list(seen_ids.values())
        results.sort(key=lambda x: x["score"], reverse=True)
        if results:
            top_score = results[0]["score"]

        domain_miss         = top_score is None or top_score < SCORE_DOMAIN_MISS
        needs_clarification = (
            not domain_miss
            and top_score is not None
            and top_score < SCORE_CLARIFICATION
        )

        return {
            "results":             results,
            "top_score":           top_score,
            "domain_miss":         domain_miss,
            "needs_clarification": needs_clarification,
        }


# ── Module-level singleton + export ──────────────────────────────────────────

_retriever = FAQRetriever()


def retrieve(query: str, top_k: int = 3) -> dict:
    """
    Public retrieval API.

    Parameters
    ----------
    query : str
        Raw user query string.
    top_k : int
        Number of candidate FAQ entries to return (default 3).

    Returns
    -------
    {
      "results": [
        {
          "id":          str,
          "section":     str,
          "question":    str,
          "answer_text": str,
          "source_url":  str,
          "score":       float
        }
      ],
      "top_score":           float | None,
      "domain_miss":         bool,
      "needs_clarification": bool
    }
    """
    return _retriever.search(query, top_k=top_k)
