"""
context_utils.py
----------------
User-context extraction helpers for the Epic Vendor Services FAQ copilot.

Kept in a leaf module (no FastAPI / memory imports) so both `main.py` and
the unit tests can import these helpers without triggering circular imports.
The `profile` argument is duck-typed (expects `.name`, `.role`, `.organization`
string attributes), so we don't need to import `UserProfile` here.
"""

from __future__ import annotations

import re


def _extract_user_context(message: str, profile) -> bool:
    """Extract name, role, org from self-identification statements. Updates profile in place."""
    changed = False
    name_patterns = [
        r"(?:i'm|i am|my name is)\s+([A-Z][a-z]+)",
    ]
    role_patterns = [
        r"(?:i'm a|i am a|i'm an|i am an|i work as an?)\s+([\w\s]+?)(?:\s+at|\s+from|\.|,|$)",
    ]
    org_patterns = [
        r"(?:i work at|i'm from|from)\s+([\w\s]+?)(?:\.|,|$)",
    ]
    for pattern in name_patterns:
        m = re.search(pattern, message, re.IGNORECASE)
        if m and not profile.name:
            profile.name = m.group(1).strip().capitalize()
            changed = True
    for pattern in role_patterns:
        m = re.search(pattern, message, re.IGNORECASE)
        if m and not profile.role:
            profile.role = m.group(1).strip()
            changed = True
    for pattern in org_patterns:
        m = re.search(pattern, message, re.IGNORECASE)
        if m and not profile.organization:
            profile.organization = m.group(1).strip()
            changed = True
    return changed


_INTRO_ONLY_PATTERNS = [
    r"^(?:hi|hello|hey)[,.]?\s+i(?:'m| am)\s+\w+",
    r"^my name is \w+",
    r"^i(?:'m| am) (?:a |an )?\w[\w\s]+$",
]


def _is_intro_only(message: str) -> bool:
    return any(re.match(p, message.strip(), re.IGNORECASE) for p in _INTRO_ONLY_PATTERNS)
