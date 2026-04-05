# Decisions Document

## Stack Choices
- **Backend**: FastAPI for async endpoint handling; lightweight, modern, and perfectly suited to wrapping retrieval scripts.
- **Frontend**: React + Vite for quick local bootstrapping with zero complex build overhead required to run; pure Typescript/React hooks.
- **Dependencies**: Restricted strictly to Python packages like SBERT and FAISS, avoiding heavy deployment infrastructure like Docker and heavy DBs to guarantee maximum portability.

## Retrieval Architecture
Our retrieval architecture uses a two-stage approach:
1. **Bloom filter**: Used as a domain guard (not a perf optimization). It immediately rejects queries that share absolutely zero lexical overlap with our terminology, returning a domain miss instead of an irrelevant low-confidence prediction.
2. **FAISS for similarity**: We use `all-MiniLM-L6-v2` encoded via SBERT. We restrict to `faiss-cpu` with `IndexFlatIP`. Vectors are L2 normalized to ensure inner product equals cosine similarity.

## Memory Design
We implemented a deque-backed conversation memory (`ConversationMemory`) with explicit UX visibility.
Visibility in the UX (the "Memory Indicator" pill) was a deliberate design choice so users can trust that the agent isn't hallucinating references and understand when it carries forward context.

## Scope Tradeoffs
- **Authentication**: No auth is implemented whatsoever to keep the application highly portable and localized.
- **HIPAA Data**: Synthetic handling only. A specific domain rule instantly rejects inquiries asking to process or handle HIPAA data since this is a local sandbox tool.
- **LLM Dependency**: Since standard usage is completely local/template-based to guarantee function offline, we accept the tradeoff that multi-source synthesis is slightly rigid compared to GPT-4o-mini, unless the fallback OpenAI key is exported.
- **LRU embedding cache** — O(1) repeated query lookup avoids re-running the 22ms SBERT forward pass for identical queries. Bounded at 128 entries (~50KB memory). Cache stats exposed via /health.

## Query Expansion on Low Confidence
When the retriever returns domain_miss=True or needs_clarification=True,
the /chat and /chat/stream endpoints check session memory for the most
recent prior user turn. If found, it prepends that turn to the current
query and retries retrieval once:

  expanded_query = f"{last_user_query} {current_query}"

This resolves conversational follow-ups like "what about the sandbox?"
after "what APIs are available?" without requiring the user to repeat
full context. The expansion only applies when the first retrieval attempt
fails — it does not run on confident retrievals, so there is zero latency
cost on the happy path.

This was added as an unprompted enhancement during implementation.
