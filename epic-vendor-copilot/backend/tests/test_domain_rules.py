import pytest
from backend.domain_rules import check_domain_rules

class TestDomainRules:
    def test_password_triggers_admin_route(self):
        res = check_domain_rules("I forgot my password")
        assert res is not None
        assert res["route"] == "admin_escalation"
        assert "credentials" in res["response"].lower()

    def test_enroll_triggers_enrollment_route(self):
        res = check_domain_rules("how do I enroll?")
        assert res is not None
        assert res["route"] == "enrollment"

    def test_hipaa_triggers_hipaa_route(self):
        res = check_domain_rules("do you support hipaa compliance?")
        assert res is not None
        assert res["route"] == "hipaa"

    def test_normal_query_returns_none(self):
        res = check_domain_rules("what is vendor services?")
        assert res is None
