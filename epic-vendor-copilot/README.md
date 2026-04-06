# Epic Vendor Copilot

## Quick Start (≤ 10 minutes)

### Prerequisites
- Python 3.10+ 
- Node.js 18+
- Git

### 1. Clone the repository

```bash
git clone https://github.com/navy1999/FAQ_Project.git
cd FAQ_Project/epic-vendor-copilot
```

### 2. Backend setup

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# If you see an execution policy error, run once:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

> **First-run note:** `pip install` will download the
> `all-MiniLM-L6-v2` sentence-transformers model (~80 MB) on
> first startup. Subsequent starts are instant (model is cached
> in `~/.cache/huggingface/` on macOS/Linux or
> `%USERPROFILE%\.cache\huggingface\` on Windows).
> Allow ~2–3 minutes on first run.

### 3. Frontend setup (new terminal)

**macOS / Linux / Windows:**
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173 in your browser.

### 4. (Optional) Enable LLM mode

By default the app runs fully offline in **template mode**.
To switch to LLM-powered responses, set the `OPENROUTER_API_KEY`
environment variable before starting the backend:

**macOS / Linux:**
```bash
export OPENROUTER_API_KEY=sk-or-v1-your-key-here
uvicorn backend.main:app --reload --port 8000
```

**Windows (PowerShell):**
```powershell
$env:OPENROUTER_API_KEY = "sk-or-v1-your-key-here"
uvicorn backend.main:app --reload --port 8000
```

**Windows (Command Prompt):**
```cmd
set OPENROUTER_API_KEY=sk-or-v1-your-key-here
uvicorn backend.main:app --reload --port 8000
```

The app detects the key at startup and switches automatically.
The `/health` endpoint will show `"mode": "llm"` when active.
No code changes required — just set the variable and restart.

## Running Tests

**macOS / Linux:**
```bash
pytest backend/tests/ -v
```

**Windows:**
```powershell
pytest backend/tests/ -v
```

## Architecture
The application runs incoming questions through a **Bloom filter** that acts as a fast domain guard rejecting clearly off-topic queries immediately. Valid queries proceed to **FAISS** for dense vector similarity retrieval using SBERT embeddings to locate the best FAQ matches. Any follow-up questions leverage semantic **memory** to retain context. If the raw query matches predefined security or routing keywords, **domain rules** instantly provide a deterministic answer. Finally, the gathered context is synthesized into a final response by either passing it through an **LLM** (if an OpenRouter key is configured) or by streaming a deterministic **template** response natively without needing an internet connection. 

> See [DECISIONS.md](./DECISIONS.md) for full stack rationale,
> DSA design decisions, and scope tradeoffs.

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

## Seed Data
To regenerate seed data from the live Epic Vendor Services FAQ:
```bash
python scrape_faq.py
```
