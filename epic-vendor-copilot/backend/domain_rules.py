"""
domain_rules.py
---------------
Pre-retrieval domain routing rules for Epic Vendor Services FAQ copilot.

Implements check_domain_rules(query) which runs BEFORE any retrieval stage.
Uses case-insensitive substring matching to detect queries that should be
routed to a canned response instead of the retrieval pipeline.

No FastAPI imports — importable standalone.
"""


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
            "enroll", "sign up", "register", "get access",
            "i'm interested", "how to join",
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


def check_domain_rules(query: str) -> dict | None:
    """
    Check a user query against pre-defined domain routing rules.

    Returns {"route": str, "response": str} on the first match,
    or None if no rule matches.

    Matching is case-insensitive substring search against the query.
    Rules are evaluated in priority order: admin_escalation → enrollment → hipaa.
    """
    query_lower = query.lower()
    for rule in _RULES:
        for trigger in rule["triggers"]:
            if trigger in query_lower:
                return {"route": rule["route"], "response": rule["response"]}
    return None
