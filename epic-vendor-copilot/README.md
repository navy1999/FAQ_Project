# Epic Vendor Copilot

A domain-scoped FAQ chatbot for [Epic Vendor Services](https://vendorservices.epic.com/FAQ/Index), powered by SBERT + FAISS semantic retrieval with an optional LLM synthesis layer via OpenRouter.

---

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

---

## Running Tests

### Unit tests (pytest)

**macOS / Linux:**
```bash
pytest backend/tests/ -v
```

**Windows:**
```powershell
pytest backend/tests/ -v
```

### End-to-end query test suite

A comprehensive 120+ case integration test suite lives in `tests/run_query_tests.py`.
It covers every FAQ topic, out-of-domain refusals, and ambiguous/clarification edge cases,
and reports `PASS` / `WARN` (right outcome, wrong FAQ entry) / `FAIL` per query.

**Step 1 — Generate the test file** (paste once into PowerShell from the project root):

```powershell
# saves tests\run_query_tests.py
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/navy1999/FAQ_Project/main/epic-vendor-copilot/tests/run_query_tests.py" -OutFile "tests\run_query_tests.py"
```

Or create the `tests/` directory and place `run_query_tests.py` there manually.

**Step 2 — Run it:**

```powershell
.\.venv\Scripts\python.exe tests\run_query_tests.py
```

**macOS / Linux:**
```bash
.venv/bin/python tests/run_query_tests.py
```

Result codes:

| Code | Meaning | Action |
|---|---|---|
| `PASS` | Correct outcome + correct FAQ id returned | ✅ Nothing |
| `WARN` | Right outcome, but wrong FAQ entry ranked first | Fix scoring / boost weights |
| `FAIL` | Entirely wrong outcome (refused an answerable query, etc.) | Fix domain rules, retriever, or clarify thresholds |

The script exits with code `1` if any FAILs exist, making it CI-compatible.

To adjust the score threshold used to classify a retriever result as an ANSWER,
edit `SCORE_THRESHOLD = 0.30` at the top of `tests/run_query_tests.py`.

---

## Architecture

The application evaluates incoming questions using **semantic score thresholding** powered by SBERT and FAISS.

```
User Query
    │
    ▼
domain_rules.py ──► Bloom filter + Trie keyword pre-screen
    │                  (fast O(1) in-domain signal)
    ▼
retriever.py ──────► SBERT encode → FAISS cosine search → top-k results
    │
    ▼
main.py ───────────► Two-tier confidence gate:
    │                  Score < 0.45  → domain_miss  (refuse, out-of-domain)
    │                  Score < 0.72  → needs_clarification (ask for more detail)
    │                  Score ≥ 0.72  → confident match
    ▼
synthesizer.py ────► Template engine (offline) or LLM via OpenRouter (if key set)
    │
    ▼
memory.py ─────────► Short-term session context: resolves follow-up queries
                      (e.g. "how much?" after an enrollment question)
                      by expanding low-scoring vague queries with prior turns
```

> See [DECISIONS.md](./DECISIONS.md) for full stack rationale,
> DSA design decisions, and scope tradeoffs.

---

## Project Structure

```
epic-vendor-copilot/
├── backend/
│   ├── main.py            # FastAPI app, routing, confidence gate
│   ├── retriever.py       # SBERT + FAISS semantic search
│   ├── domain_rules.py    # Bloom filter + Trie keyword pre-screen
│   ├── synthesizer.py     # Template / LLM response synthesis
│   ├── memory.py          # Short-term session memory
│   └── tests/             # pytest unit tests
├── frontend/              # Vite + React UI
├── SEED_DATA/             # Scraped FAQ JSON (32 entries, 11 sections)
├── tests/
│   └── run_query_tests.py # 120+ case end-to-end query test suite
├── scrape_faq.py          # Re-scrapes live Epic FAQ → SEED_DATA/
├── diagnose.py            # Quick domain_rules + retriever spot-check
├── requirements.txt
├── DECISIONS.md
├── TESTING.md
└── AI_USAGE.md
```

---

## Modes

| Feature | Template Mode (no key) | LLM Mode (OPENROUTER_API_KEY set) |
| --- | --- | --- |
| **Synthesis** | Deterministic fallback using templates | Context-aware synthesis |
| **Dependency** | 100% Local / Offline | Needs internet + valid API key |
| **Memory** | Appends turns cleanly | Instructs LLM context window natively |

---

## Scope Tradeoffs

- **Authentication**: No auth implemented — keeps the app fully portable and self-contained.
- **Privacy**: No PII/HIPAA data handling. Sandbox tool for FAQ retrieval only.
- **Local-First**: Designed to function 100% offline via template mode, accepting slightly less flexible phrasing in exchange for zero internet dependency.

---

## Seed Data

To regenerate seed data from the live Epic Vendor Services FAQ:
```bash
python scrape_faq.py
```

Data is fetched from the public JSON endpoint at
`https://vendorservices.epic.com/FAQ/GetAllFaqItemDocuments`
(no authentication required) and written to `SEED_DATA/`.
