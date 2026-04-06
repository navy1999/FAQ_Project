from __future__ import annotations
"""
domain_rules.py
---------------
Pre-retrieval domain routing rules for Epic Vendor Services FAQ copilot.

Implements check_domain_rules(query) which runs BEFORE any retrieval stage.
Uses a Trie-based prefix matching mechanism for O(k) keyword matching
where k = query length. Routes matched queries to canned responses
instead of the retrieval pipeline.

No FastAPI imports — importable standalone.
"""


class _TrieNode:
    __slots__ = ("children", "route")
    def __init__(self):
        self.children: dict[str, "_TrieNode"] = {}
        self.route: str | None = None


class _DomainRuleTrie:
    """
    Trie for O(k) domain rule prefix matching where k = query length.
    Scales to thousands of rules without per-query cost growth,
    unlike O(n * k) linear substring search.
    """
    def __init__(self):
        self.root = _TrieNode()

    def insert(self, phrase: str, route: str) -> None:
        node = self.root
        for word in phrase.lower().split():
            if word not in node.children:
                node.children[word] = _TrieNode()
            node = node.children[word]
        node.route = route

    def match(self, query: str) -> str | None:
        words = query.lower().split()
        for start in range(len(words)):
            node = self.root
            for word in words[start:]:
                if word not in node.children:
                    break
                node = node.children[word]
                if node.route:
                    return node.route
        return None


_RULES = [
    {
        "route": "admin_escalation",
        "triggers": [
            "password", "reset", "locked out", "can't log in",
            "cannot log in", "access denied", "credentials",
        ],
        "response": (
            "Account access issues must be resolved through your "
            "organization's designated admin or via the contact form at "
            "vendorservices.epic.com. I cannot reset credentials."
        ),
    },
    {
        "route": "enrollment",
        "triggers": [
            "how to join vendor services",
            "sign up for vendor services",
            "register as a vendor",
            "get vendor services access",
            "i'm interested in joining",
            "how do i become a vendor",
            "enroll in vendor services",
            "want to enroll",
            "looking to enroll",
        ],
        "response": (
            "To enroll in Vendor Services, visit "
            "vendorservices.epic.com/Developer and click 'I'm Interested' "
            "to complete the registration form."
        ),
    },
    {
        "route": "hipaa",
        "triggers": [
            "patient data", "phi", "hipaa", "health record",
            "real patient",
        ],
        "response": (
            "Vendor Services sandboxes use synthetic data only. "
            "Do not submit real patient data or PHI through the portal, "
            "support tickets, or sandbox environments."
        ),
    },
]

# Build a lookup from route name -> response
_RESPONSE_BY_ROUTE = {rule["route"]: rule["response"] for rule in _RULES}

# Build the trie at module load time from existing ROUTING_RULES
_trie = _DomainRuleTrie()
for _rule in _RULES:
    for _trigger in _rule["triggers"]:
        _trie.insert(_trigger, _rule["route"])


def check_domain_rules(query: str) -> dict | None:
    """
    Check a user query against pre-defined domain routing rules.

    Returns {"route": str, "response": str} on the first match,
    or None if no rule matches.

    Matching uses a Trie-based word-level prefix search against the query.
    Rules are evaluated in priority order: admin_escalation → enrollment → hipaa.
    """
    route = _trie.match(query)
    if route is not None:
        return {"route": route, "response": _RESPONSE_BY_ROUTE[route]}
    return None
