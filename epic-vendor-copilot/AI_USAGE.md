# AI Usage Documentation

This project was built with the assistance of several AI tools in specific, isolated capacities to accelerate development while ensuring human oversight over all architectural decisions.

1. **Cursor Agent** was used to rapidly scaffold boilerplate file stubs and organize the primary folder layouts for both the FastAPI backend and the React frontend.
2. **Perplexity** served as a research assistant — specifically for evaluating whether an external database like PostgreSQL was necessary versus using flat-file FAISS indexes, and for architectural planning of the retrieval pipeline.
3. The core logic — `retriever.py` FAISS indexing, `domain_rules.py` Bloom filter + Trie construction, and `responder.py` template/LLM routing — was directly human-directed.
4. The **OpenRouter/Qwen3** integration was strictly human-directed. The fallback and provider priority logic (evaluating `OPENROUTER_API_KEY` presence → Qwen3 via OpenRouter → offline template fallback) was explicitly written and constrained manually.

---

## Architectural Overview

The system uses a **three-layer pipeline** that has remained stable since initial design:

1. **Bloom filter + Trie pre-screen** (`domain_rules.py`): Fast O(k) lexical domain guard. Immediately rejects queries with zero overlap with the FAQ corpus before any vector computation.
2. **SBERT + FAISS semantic retrieval** (`retriever.py`): Dense vector similarity search over the 32-entry FAQ corpus using `all-MiniLM-L6-v2` + `faiss-cpu` `IndexFlatIP`.
3. **Two-tier confidence gate** (`main.py`): Score < 0.45 → refuse; score < 0.72 → clarify; score ≥ 0.72 → answer.

All three layers are active in the current codebase. There is no architectural component that has been removed or replaced — the Bloom filter, Trie, and semantic score thresholding coexist as complementary guards.

---

## Observability Note

The `/health` endpoint intentionally exposes internal cache statistics (`_CACHE_STATS`: hits, misses, cache size) and session counts. This is deliberate for evaluation purposes — it lets a reviewer verify the LRU cache and session eviction are functioning without attaching a debugger. In a production deployment these fields would be gated behind an internal-only route or removed entirely.

---

## Test Suite Note

The end-to-end query test suite (`tests/run_query_tests.py`) was co-developed with Perplexity to cover the full FAQ corpus with 120+ queries across every topic category, out-of-domain refusals, and ambiguous edge cases. All expected FAQ entry IDs (`vs-XXXX`) were verified against the live seed data in `SEED_DATA/`. Final review and validation of expected outcomes was human-directed.
