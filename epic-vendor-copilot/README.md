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
The application evaluates incoming questions using **semantic score thresholding** powered by SBERT and FAISS. 

1. **Retriever**: Queries are encoded using the `all-MiniLM-L6-v2` model.
2. **Routing**: `main.py` applies a two-tier confidence gate:
   - **Score < 0.45**: Immediate rejection as out-of-domain.
   - **Score < 0.72**: Trigger a clarification request asking for more detail.
   - **Score >= 0.72**: Processed as a confident match.
3. **Synthesis**: Gathered FAQ context is then synthesized into a response via **LLM** (if an OpenRouter key is set) or a local deterministic **template** engine. 
4. **Memory**: Short-term session memory allows the system to resolve follow-up questions (e.g., "how much?" after an enrollment question) by expanding vague queries with prior context when first-pass scores are low.

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
- **Privacy**: No PII/HIPAA data handling. The system is a sandbox tool for FAQ retrieval only.
- **Local-First**: The application is designed to function 100% offline via template mode, accepting slightly less flexible phrasing in exchange for zero internet dependency.

## Seed Data
To regenerate seed data from the live Epic Vendor Services FAQ:
```bash
python scrape_faq.py
```
