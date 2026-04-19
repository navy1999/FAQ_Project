"""
domain_rules.py
---------------
Pre-retrieval domain gate for the Epic Vendor Services FAQ copilot.

Architecture:
  Two data structures run in order before FAISS is consulted:

  1. Bloom filter  — probabilistic set-membership check on normalised tokens.
     A token present in the filter MAY be a known keyword; a token absent
     definitely is not.  False-positive rate ≈ 0.1 % at the current capacity.

  2. Trie (prefix tree) — exact keyword/phrase lookup used to:
       a. confirm a Bloom hit (eliminates false positives), and
       b. map the matched keyword to a routing action.

Routing actions
  "enrollment"       — direct user to the enrollment/sign-up FAQ section
  "admin_escalation" — direct user to contact their Epic admin (password / access)
  "boundary"         — politely decline (HIPAA, PHI, clinical topics)
  None               — no domain-rule match; fall through to FAISS retrieval

Design rationale (see DECISIONS.md §Domain Gate)
  The Bloom filter lets the hot path skip all Trie traversal for the vast
  majority of queries that contain no known trigger terms.  This keeps
  median latency under 1 ms even when the Trie grows to hundreds of entries.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Optional


# ── Bloom filter ─────────────────────────────────────────────────────────────

class _BloomFilter:
    """
    Minimal Bloom filter backed by a Python bytearray.

    Parameters
    ----------
    capacity : int
        Expected number of distinct items to insert.
    error_rate : float
        Desired false-positive probability (0 < error_rate < 1).
    """

    def __init__(self, capacity: int = 256, error_rate: float = 0.001) -> None:
        self._size = self._optimal_size(capacity, error_rate)
        self._hash_count = self._optimal_hashes(self._size, capacity)
        self._bits = bytearray(math.ceil(self._size / 8))

    # ── internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _optimal_size(n: int, p: float) -> int:
        return max(64, int(-(n * math.log(p)) / (math.log(2) ** 2)))

    @staticmethod
    def _optimal_hashes(m: int, n: int) -> int:
        return max(1, round((m / n) * math.log(2)))

    def _positions(self, item: str):
        """Yield *self._hash_count* bit positions for *item*."""
        import hashlib
        h1 = int(hashlib.md5(item.encode()).hexdigest(), 16)   # noqa: S324
        h2 = int(hashlib.sha1(item.encode()).hexdigest(), 16)  # noqa: S324
        for i in range(self._hash_count):
            yield (h1 + i * h2) % self._size

    # ── public API ────────────────────────────────────────────────────────────

    def add(self, item: str) -> None:
        for pos in self._positions(item):
            self._bits[pos >> 3] |= 1 << (pos & 7)

    def __contains__(self, item: str) -> bool:
        return all(
            (self._bits[pos >> 3] >> (pos & 7)) & 1
            for pos in self._positions(item)
        )


# ── Trie ──────────────────────────────────────────────────────────────────────

class _TrieNode:
    __slots__ = ("children", "action")

    def __init__(self) -> None:
        self.children: dict[str, "_TrieNode"] = {}
        self.action: Optional[str] = None


class _Trie:
    """Prefix trie mapping normalised keyword/phrase → routing action."""

    def __init__(self) -> None:
        self._root = _TrieNode()

    def insert(self, phrase: str, action: str) -> None:
        node = self._root
        for token in phrase.split():
            node = node.children.setdefault(token, _TrieNode())
        node.action = action

    def search(self, tokens: list[str]) -> Optional[str]:
        """
        Slide a window over *tokens* and return the action for the first
        matching phrase, or None if no phrase matches.
        """
        for start in range(len(tokens)):
            node = self._root
            for token in tokens[start:]:
                node = node.children.get(token)  # type: ignore[assignment]
                if node is None:
                    break
                if node.action is not None:
                    return node.action
        return None


VAGUE_QUERIES: frozenset[str] = frozenset({
    "help", "info", "hi", "hello", "hey", "yes", "no", "ok",
    "okay", "sure", "tell me more", "more info", "go on",
    "continue", "what else", "more", "next", "thanks",
})

_OOD_HARD_BLOCK: tuple[str, ...] = (
    "stock price", "weather", "recipe", "cook", "movie", "film",
    "translate", "translation", "sports score", "super bowl",
    "nfl", "nba", "stock market", "cryptocurrency", "bitcoin",
    "poem", "joke", "news headlines", "horoscope",
)

# ── Keyword table ─────────────────────────────────────────────────────────────
#
# Format: (phrase, action)
# Phrases are lower-cased, whitespace-normalised tokens joined by spaces.
# Single-token entries double as Bloom filter seeds.

_KEYWORD_TABLE: list[tuple[str, str]] = [
    # Enrollment / sign-up
    ("enroll",               "enrollment"),
    ("enrollment",           "enrollment"),
    ("sign up",              "enrollment"),
    ("sign-up",              "enrollment"),
    ("register",             "enrollment"),
    ("registration",         "enrollment"),
    ("get started",          "enrollment"),
    ("join",                 "enrollment"),
    ("onboard",              "enrollment"),
    ("onboarding",           "enrollment"),
    ("new vendor",           "enrollment"),
    ("become a vendor",      "enrollment"),
    ("vendor application",   "enrollment"),
    ("apply",                "enrollment"),
    ("application",          "enrollment"),
    ("subscribe",            "enrollment"),
    ("subscription",         "enrollment"),
    ("activate",             "enrollment"),
    ("activation",           "enrollment"),
    # Access / password / admin
    ("password",             "admin_escalation"),
    ("reset password",       "admin_escalation"),
    ("forgot password",      "admin_escalation"),
    ("login",                "admin_escalation"),
    ("log in",               "admin_escalation"),
    ("sign in",              "admin_escalation"),
    ("access",               "admin_escalation"),
    ("locked out",           "admin_escalation"),
    ("account locked",       "admin_escalation"),
    ("unlock account",       "admin_escalation"),
    ("credentials",          "admin_escalation"),
    ("username",             "admin_escalation"),
    ("two factor",           "admin_escalation"),
    ("2fa",                  "admin_escalation"),
    ("mfa",                  "admin_escalation"),
    ("multi factor",         "admin_escalation"),
    ("sso",                  "admin_escalation"),
    ("single sign on",       "admin_escalation"),
    ("single sign-on",       "admin_escalation"),
    ("permissions",          "admin_escalation"),
    ("role",                 "admin_escalation"),
    # Domain boundary (clinical / HIPAA)
    ("hipaa",                "boundary"),
    ("phi",                  "boundary"),
    ("ehr",                  "boundary"),
    ("epic ehr",             "boundary"),
    ("medical record",       "boundary"),
]


# Compound-context boundary rules: single clinical words like "treatment" or
# "clinical" no longer block on their own (too many false positives for
# legitimate vendor queries such as "treatment process for a rejected claim").
# A boundary refusal now requires BOTH tokens of a rule to co-occur anywhere
# in the query.
_BOUNDARY_COMPOUND_RULES: list[frozenset] = [
    frozenset({"treatment", "patient"}),
    frozenset({"clinical", "diagnosis"}),
    frozenset({"treatment", "medical"}),
    frozenset({"patient", "record"}),
    frozenset({"clinical", "trial"}),
]


def _check_compound_boundary(tokens: list[str]) -> bool:
    token_set = frozenset(tokens)
    return any(rule.issubset(token_set) for rule in _BOUNDARY_COMPOUND_RULES)


# ── Module initialisation ─────────────────────────────────────────────────────

_bloom = _BloomFilter(capacity=len(_KEYWORD_TABLE) * 4, error_rate=0.001)
_trie = _Trie()

for _phrase, _action in _KEYWORD_TABLE:
    # Seed Bloom filter with every individual token in the phrase
    for _tok in _phrase.split():
        _bloom.add(_tok)
    # Insert full phrase into Trie
    _trie.insert(_phrase, _action)


# ── Public API ────────────────────────────────────────────────────────────────

def _normalise(text: str) -> list[str]:
    """Lower-case, NFKC-normalise, strip punctuation, split on whitespace."""
    text = unicodedata.normalize("NFKC", text.lower().strip())
    text = re.sub(r"[^\w\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.split()


def check_domain_rules(query: str) -> Optional[str]:
    """
    Check *query* against the pre-retrieval domain gate.

    Returns
    -------
    str | None
        A routing action string if a domain rule matches, otherwise None.

    Routing actions
    ---------------
    "enrollment"       Steer user to enrollment / sign-up FAQ section.
    "admin_escalation" Instruct user to contact their Epic admin for
                       password / access issues.
    "boundary"         Decline politely; topic is out of scope (HIPAA etc.).
    None               No rule matched; proceed to FAISS semantic retrieval.
    """
    q_lower = query.strip().lower()

    # Guard 1: vague single-word or known vague phrase → clarify
    tokens_preview = q_lower.split()
    if q_lower in VAGUE_QUERIES or (len(tokens_preview) <= 1 and len(q_lower) <= 5):
        return "vague"

    # Guard 2: hard OOD patterns → domain_miss
    if any(pattern in q_lower for pattern in _OOD_HARD_BLOCK):
        return "ood_hard_block"

    tokens = _normalise(query)
    if not tokens:
        return None

    # Fast path: skip Trie entirely if no token is in the Bloom filter.
    # Compound-boundary rules are checked even on the fast path, since their
    # tokens (e.g. "treatment", "patient") are no longer seeded in the Bloom
    # filter.
    if not any(tok in _bloom for tok in tokens):
        if _check_compound_boundary(tokens):
            return "boundary"
        return None

    # Slow path: confirm via Trie (eliminates Bloom false positives)
    trie_result = _trie.search(tokens)
    if trie_result is not None:
        return trie_result
    if _check_compound_boundary(tokens):
        return "boundary"
    return None
