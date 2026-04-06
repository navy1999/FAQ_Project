# AI Usage Documentation

This project was built with the assistance of several AI tools in specific, isolated capacities to accelerate development while ensuring human oversight over architectural decisions.

1. **Cursor Agent** was utilized initially to rapidly scaffold the necessary boilerplate file stubs and organize the primary folder layouts for both the FastAPI backend and the React frontend.
2. **Perplexity** served as a research assistant, specifically leveraged for architectural planning and evaluating whether an external database like Postgres was necessary versus using flat-file FAISS indexes.
3. The vast majority of the core logic, specifically involving the `retriever.py` Bloom filter implementation, FAISS clustering, and `responder.py` custom logic, was directly human-directed. The AI assistants were generally restricted to auto-completing React component stylings, generating basic CSS structures, and scaffolding standard boilerplate test cases.
4. The integration with **OpenRouter/Qwen3** was highly structured and strictly human-directed. Specifically, the fallback and provider priority logic mapping between evaluating `OPENROUTER_API_KEY` presence to default to Qwen3 before relying on the offline template response paths was explicitly written and constrained manually by the developers.

## Observability Note

The `/health` endpoint intentionally exposes internal cache statistics
(`_CACHE_STATS`: hits, misses, cache size) and session counts. This is
deliberate for evaluation purposes — it lets a reviewer verify the
LRU cache and session eviction are functioning without needing to attach
a debugger. In a production deployment these fields would be gated behind
an internal-only route or removed.
