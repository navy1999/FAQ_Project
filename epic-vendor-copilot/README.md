# Epic Vendor Copilot

## Quick Start (≤10 minutes)
Exact commands:
```bash
git clone https://github.com/your-repo/epic-vendor-copilot.git
cd epic-vendor-copilot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Optional: export OPENROUTER_API_KEY=sk-or-v1-...
uvicorn backend.main:app --reload --port 8000
```
New terminal:
```bash
cd frontend && npm install && npm run dev
```

## Running Tests
```bash
pytest backend/tests/ -v
```

## Architecture
The application runs incoming questions through a **Bloom filter** acts as a fast domain guard rejecting clearly off-topic queries immediately. Valid queries proceed to **FAISS** for dense vector similarity retrieval using SBERT embeddings to locate the best FAQ matches. Any follow-up questions leverage semantic **memory** to retain context. If the raw query matches predefined security or routing keywords, **domain rules** instantly provide a deterministic answer. Finally, the gathered context is synthesized into a final response by either passing it through an **LLM** (if an OpenRouter key is configured) or by streaming a deterministic **template** response natively without needing an internet connection. 

## Modes
| Feature | Template Mode (no key) | LLM Mode (OPENROUTER_API_KEY set) |
| --- | --- | --- |
| **Synthesis** | Deterministic fallback using templates | Context-aware synthesis |
| **Dependency** | 100% Local / Offline | Needs Internet and valid API key |
| **Memory** | Appends turns cleanly | Instructs LLM context windows natively |

## Scope Tradeoffs
- **Authentication**: No auth is implemented whatsoever to keep the application highly portable and localized.
- **HIPAA Data**: Synthetic handling only. A specific domain rule instantly rejects inquiries asking to process or handle HIPAA data since this is a local sandbox tool.
- **LLM Dependency**: Since standard usage is completely local/template-based to guarantee function offline, we accept the tradeoff that multi-source synthesis is slightly rigid compared to GPT-4o-mini, unless the fallback OpenAI key is exported.
