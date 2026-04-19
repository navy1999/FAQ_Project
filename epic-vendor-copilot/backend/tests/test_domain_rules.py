"""
test_domain_rules.py
--------------------
Unit tests for backend.domain_rules module.

Focuses on the compound-boundary rules introduced after the post-review
domain-guard update. Single clinical words (e.g. "treatment", "clinical")
no longer block on their own; a boundary refusal now requires two tokens
to co-occur.
"""

from backend.domain_rules import check_domain_rules


def test_treatment_alone_does_not_block():
    result = check_domain_rules("what is the treatment process for a rejected claim")
    assert result is None


def test_treatment_with_patient_blocks():
    result = check_domain_rules("I need treatment information for my patient")
    assert result == "boundary"


def test_clinical_billing_does_not_block():
    result = check_domain_rules("what are the clinical billing codes for vendor submissions")
    assert result is None
