"""
scrape_faq.py
-------------
Scrapes Epic Vendor Services FAQ data from the public JSON API endpoint
discovered in FaqViewModel.js: GET /FAQ/GetAllFaqItemDocuments

No authentication required. The endpoint returns JSON directly.

Run:
    python scrape_faq.py

Output:
    SEED_DATA/epic_vendor_faq.json
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

BASE_URL = "https://vendorservices.epic.com"
API_PATH = "/FAQ/GetAllFaqItemDocuments"
OUTPUT_PATH = Path("SEED_DATA/epic_vendor_faq.json")


# ── HTML → plain text ────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    """
    Minimal HTML-to-text converter.
    Inserts newlines at block-level tag boundaries so the
    plain-text answer preserves paragraph / list structure.
    """

    BLOCK_TAGS = {"p", "li", "br", "h1", "h2", "h3", "h4", "ul", "ol", "div"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text + " ")

    def get_text(self) -> str:
        raw = "".join(self.parts)
        # Collapse 3+ consecutive newlines → single blank line
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


def html_to_text(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


# ── Network fetch ─────────────────────────────────────────────────────────────

def fetch_faq_data() -> dict:
    """
    Hit the undocumented-but-public JSON endpoint that the Knockout ViewModel
    calls on page load. Headers mimic a real browser GET from the FAQ page.
    """
    url = BASE_URL + API_PATH
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": BASE_URL + "/FAQ/Index",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


# ── Data transform ────────────────────────────────────────────────────────────

def transform(raw_data: dict) -> dict:
    """
    Normalise the raw API payload into a flat, retrieval-friendly structure:

      {
        "meta": { ... },
        "sections": [
          {
            "section_id": int,
            "section": str,
            "order": int,
            "entries": [
              {
                "id": "vs-<int>",
                "question": str,
                "answer_html": str,   ← kept for rich UI rendering
                "answer_text": str,   ← used for SBERT embedding + LLM context
                "keywords": [str],
                "source_url": str,
                "section": str,
                "order": int
              },
              ...
            ]
          },
          ...
        ]
      }
    """
    payload = raw_data.get("Data", raw_data)
    categories = payload.get("categories", [])

    sections = []
    total_entries = 0

    for cat in sorted(categories, key=lambda c: c.get("Order", 0)):
        items = cat.get("Items", [])
        entries = []

        for item in sorted(items, key=lambda i: i.get("Order", 0)):
            answer_html = item.get("Answer", "")
            answer_text = html_to_text(answer_html)
            keywords_raw = item.get("Keywords", "") or ""
            keywords = [
                k.strip()
                for k in re.split(r"[;,]", keywords_raw)
                if k.strip()
            ]

            entries.append({
                "id": f"vs-{item['Id']}",
                "question": item.get("Question", "").strip(),
                "answer_html": answer_html.strip(),
                "answer_text": answer_text,
                "keywords": keywords,
                "source_url": BASE_URL + "/FAQ/Index",
                "section": cat.get("Category", ""),
                "order": item.get("Order", 0),
            })
            total_entries += 1

        sections.append({
            "section_id": cat.get("Id"),
            "section": cat.get("Category", ""),
            "order": cat.get("Order", 0),
            "entries": entries,
        })

    return {
        "meta": {
            "source": BASE_URL + "/FAQ/Index",
            "api_endpoint": BASE_URL + API_PATH,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "total_sections": len(sections),
            "total_entries": total_entries,
            "note": (
                "Data fetched from the public JSON API endpoint discovered "
                "in FaqViewModel.js (GET /FAQ/GetAllFaqItemDocuments). "
                "No authentication required."
            ),
        },
        "sections": sections,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Fetching FAQ data from {BASE_URL + API_PATH} ...")

    try:
        raw = fetch_faq_data()
    except urllib.error.URLError as exc:
        print(f"ERROR: Network failure — {exc}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Unexpected response format — {exc}", file=sys.stderr)
        sys.exit(1)

    if not raw.get("Success", True):
        print(f"ERROR: API returned failure — {raw}", file=sys.stderr)
        sys.exit(1)

    data = transform(raw)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    print(
        f"Done! Wrote {data['meta']['total_entries']} entries across "
        f"{data['meta']['total_sections']} sections → {OUTPUT_PATH}"
    )
    for section in data["sections"]:
        count = len(section["entries"])
        print(f"  [{section['section']}] — {count} question{'s' if count != 1 else ''}")


if __name__ == "__main__":
    main()
