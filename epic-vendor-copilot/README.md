# Epic Vendor Copilot

A local-portable FAQ support copilot for Epic Vendor Services built with FastAPI, React, and FAISS.

## Quick Start (≤10 minutes)
```bash
git clone <repo-url> && cd epic-vendor-copilot
python -m venv .venv && source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scrape_faq.py
cd backend && uvicorn main:app --reload --port 8000
```
In a second terminal:
```bash
cd frontend && npm install && npm run dev
```
Open http://localhost:5173

## Run Tests
```bash
pytest backend/tests/ -v
```

## Optional: LLM Mode
```bash
export OPENAI_API_KEY=sk-...
uvicorn backend.main:app --reload --port 8000
```
Without the key, the app runs in local template mode — no API key required.
