#!/usr/bin/env python3
"""
run_query_tests.py
------------------
End-to-end quality harness for the Epic Vendor FAQ retriever.
Tests every FAQ topic area, OOD refusals, and clarification edge cases.

Run from epic-vendor-copilot/:
    python tests/run_query_tests.py

Exit code 0 = all PASS/WARN. Exit code 1 = at least one FAIL.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Download NLTK data if needed
import nltk
for corpus in ("wordnet", "omw-1.4"):
    try:
        nltk.data.find(f"corpora/{corpus}")
    except LookupError:
        nltk.download(corpus, quiet=True)

from backend.retriever import retrieve

# ── Thresholds (must match main.py) ──────────────────────────────────────────
SCORE_ANSWER      = 0.72
SCORE_DOMAIN_MISS = 0.45

# ── ANSI colors ───────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

# ── Test cases ────────────────────────────────────────────────────────────────
# Format: (query, expected_outcome, expected_faq_id_or_None)
# expected_outcome: "ANSWER" | "CLARIFY" | "REFUSE"
# expected_faq_id:  None means any answer is acceptable (don't check ID)

TEST_CASES = [
    # ── What is Vendor Services ───────────────────────────────────────────────
    ("what is Epic Vendor Services",            "ANSWER", "vs-1072"),
    ("tell me about Epic Vendor Services",      "ANSWER", "vs-1072"),
    ("what does vendor services do",            "ANSWER", "vs-1072"),
    ("explain vendor services to me",           "ANSWER", "vs-1072"),
    ("overview of Epic Vendor Services",        "ANSWER", "vs-1072"),

    # ── Who uses it ───────────────────────────────────────────────────────────
    ("who uses Epic Vendor Services",           "ANSWER", "vs-1073"),
    ("what companies are Epic vendors",         "ANSWER", "vs-1073"),
    ("which vendors use Epic",                  "ANSWER", "vs-1073"),

    # ── Enrollment / sign up ──────────────────────────────────────────────────
    ("how do I enroll in vendor services",      "ANSWER", "vs-1075"),
    ("how do I sign up",                        "ANSWER", "vs-1075"),
    ("how to register as a vendor",             "ANSWER", "vs-1075"),
    ("I want to become an Epic vendor",         "ANSWER", "vs-1075"),
    ("what is the enrollment process",          "ANSWER", "vs-1075"),
    ("vendor registration steps",               "ANSWER", "vs-1075"),
    ("how to join Epic Vendor Services",        "ANSWER", "vs-1075"),
    ("sign up process for vendors",             "ANSWER", "vs-1075"),

    # ── Pricing / cost ────────────────────────────────────────────────────────
    ("how much does it cost",                   "ANSWER", "vs-1076"),
    ("what is the pricing",                     "ANSWER", "vs-1076"),
    ("vendor services fees",                    "ANSWER", "vs-1076"),
    ("how much to enroll",                      "ANSWER", "vs-1076"),
    ("what are the charges",                    "ANSWER", "vs-1076"),
    ("is there a fee",                          "ANSWER", "vs-1076"),
    ("annual subscription price",               "ANSWER", "vs-1076"),

    # ── Trial / cancel / refund ───────────────────────────────────────────────
    ("is there a free trial",                   "ANSWER", "vs-1078"),
    ("can I cancel my subscription",            "ANSWER", "vs-1078"),
    ("how do I get a refund",                   "ANSWER", "vs-1078"),
    ("cancel my account",                       "ANSWER", "vs-1078"),
    ("trial period for vendor services",        "ANSWER", "vs-1078"),

    # ── Login / password / access ─────────────────────────────────────────────
    ("how do I log in",                         "ANSWER", None),
    ("I forgot my password",                    "ANSWER", None),
    ("how to reset password",                   "ANSWER", None),
    ("login issues",                            "ANSWER", None),
    ("can't sign in to vendor services",        "ANSWER", None),
    ("account access problems",                 "ANSWER", None),
    ("who manages user access",                 "ANSWER", None),
    ("how do I add a new user",                 "ANSWER", None),

    # ── Account setup timing ──────────────────────────────────────────────────
    ("how long does account setup take",        "ANSWER", "vs-1278"),
    ("when will my account be ready",           "ANSWER", "vs-1278"),
    ("account activation time",                 "ANSWER", "vs-1278"),
    ("how long until I can log in after enrolling", "ANSWER", "vs-1278"),

    # ── FHIR / APIs / standards ───────────────────────────────────────────────
    ("does Epic support FHIR",                  "ANSWER", None),
    ("what APIs does Epic support",             "ANSWER", None),
    ("FHIR R4 compatibility",                   "ANSWER", None),
    ("how to use Epic FHIR APIs",               "ANSWER", None),
    ("HL7 support",                             "ANSWER", None),
    ("SMART on FHIR",                           "ANSWER", None),
    ("REST API documentation",                  "ANSWER", None),

    # ── open.epic / Epic on FHIR ──────────────────────────────────────────────
    ("what is open.epic",                       "ANSWER", None),
    ("Epic on FHIR portal",                     "ANSWER", None),
    ("open epic developer resources",           "ANSWER", None),

    # ── Learning / networking ─────────────────────────────────────────────────
    ("what learning resources are available",   "ANSWER", "vs-1100"),
    ("is there training for vendors",           "ANSWER", "vs-1100"),
    ("Epic UGM conference",                     "ANSWER", "vs-1100"),
    ("vendor networking opportunities",         "ANSWER", "vs-1100"),
    ("online learning portal",                  "ANSWER", "vs-1100"),

    # ── Testing tools ─────────────────────────────────────────────────────────
    ("are there testing tools",                 "ANSWER", "vs-1240"),
    ("sandbox environment for testing",         "ANSWER", "vs-1240"),
    ("test my integration with Epic",           "ANSWER", "vs-1240"),
    ("testing sandbox access",                  "ANSWER", "vs-1240"),

    # ── Contact / support ─────────────────────────────────────────────────────
    ("how do I contact Epic support",           "ANSWER", None),
    ("vendor services contact information",     "ANSWER", None),
    ("how to reach Epic",                       "ANSWER", None),
    ("support phone number",                    "ANSWER", None),
    ("email Epic vendor services",              "ANSWER", None),

    # ── Analytics / Caboodle ──────────────────────────────────────────────────
    ("does Epic support analytics",             "ANSWER", "vs-1097"),
    ("Caboodle data warehouse",                 "ANSWER", "vs-1097"),
    ("data analytics capabilities",             "ANSWER", "vs-1097"),
    ("machine learning with Epic data",         "ANSWER", "vs-1097"),

    # ── Marketing / Connection Hub ────────────────────────────────────────────
    ("what is Connection Hub",                  "ANSWER", None),
    ("how to market my Epic integration",       "ANSWER", None),
    ("vendor showroom listing",                 "ANSWER", None),

    # ── Showroom tiers ────────────────────────────────────────────────────────
    ("what are the showroom tiers",             "ANSWER", None),
    ("difference between showroom levels",      "ANSWER", None),
    ("Gold Silver Bronze vendor tiers",         "ANSWER", None),

    # ── Out-of-domain (should REFUSE) ────────────────────────────────────────
    ("what is the weather today",               "REFUSE", None),
    ("write me a poem",                         "REFUSE", None),
    ("who won the Super Bowl",                  "REFUSE", None),
    ("tell me a joke",                          "REFUSE", None),
    ("stock price of Apple",                    "REFUSE", None),
    ("how do I cook pasta",                     "REFUSE", None),
    ("what is quantum computing",               "REFUSE", None),
    ("recommend a movie",                       "REFUSE", None),
    ("translate hello to French",               "REFUSE", None),
    ("latest news headlines",                   "REFUSE", None),

    # ── Ambiguous / vague (should CLARIFY) ───────────────────────────────────
    ("help",                                    "CLARIFY", None),
    ("I have a question",                       "CLARIFY", None),
    ("something is wrong",                      "CLARIFY", None),
    ("info",                                    "CLARIFY", None),
    ("tell me more",                            "CLARIFY", None),
]


def classify(result: dict) -> str:
    """Classify a retriever result into ANSWER / CLARIFY / REFUSE."""
    score = result.get("top_score")
    if score is None or score < SCORE_DOMAIN_MISS:
        return "REFUSE"
    if score < SCORE_ANSWER:
        return "CLARIFY"
    return "ANSWER"


def run():
    passes = warns = fails = 0
    fail_cases = []

    header = f"\n{'─'*70}\n{'QUERY':45} {'EXPECT':8} {'GOT':8} {'SCORE':7} {'TOP_ID':12} STATUS\n{'─'*70}"
    print(header)

    for query, expected, expected_id in TEST_CASES:
        result    = retrieve(query)
        outcome   = classify(result)
        score     = result.get("top_score") or 0.0
        top_id    = result["results"][0]["id"] if result.get("results") else "—"

        # Determine pass/warn/fail
        if outcome != expected:
            status = f"{RED}FAIL{RESET}"
            fails += 1
            fail_cases.append((query, expected, outcome, score, top_id))
        elif expected_id and top_id != expected_id:
            status = f"{YELLOW}WARN{RESET}"
            warns += 1
        else:
            status = f"{GREEN}PASS{RESET}"
            passes += 1

        q_trunc = query[:44]
        print(f"{q_trunc:45} {expected:8} {outcome:8} {score:6.4f}  {top_id:12} {status}")

    print(f"\n{'─'*70}")
    print(f"{BOLD}Results: {GREEN}{passes} PASS{RESET}  {YELLOW}{warns} WARN{RESET}  {RED}{fails} FAIL{RESET}{RESET}  (total: {len(TEST_CASES)})")

    if fail_cases:
        print(f"\n{RED}{BOLD}Failed cases:{RESET}")
        for q, exp, got, sc, tid in fail_cases:
            print(f"  [{RED}FAIL{RESET}] \"{q}\"  expected={exp}  got={got}  score={sc:.4f}  top_id={tid}")
        sys.exit(1)
    else:
        print(f"\n{GREEN}All tests passed (WARNs are acceptable — right outcome, different FAQ entry).{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    run()