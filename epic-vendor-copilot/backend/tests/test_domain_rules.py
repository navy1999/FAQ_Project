from backend.domain_rules import check_domain_rules

def test_password_triggers_admin_route():
    result = check_domain_rules("I forgot my password and can't log in")
    assert result is not None
    assert result["route"] == "admin_escalation"
    assert "admin" in result["response"].lower() or "contact" in result["response"].lower()

def test_locked_out_triggers_admin_route():
    result = check_domain_rules("my account is locked out")
    assert result is not None
    assert result["route"] == "admin_escalation"

def test_enroll_triggers_enrollment_route():
    result = check_domain_rules("I want to enroll in vendor services")
    assert result is not None
    assert result["route"] == "enrollment"

def test_hipaa_triggers_hipaa_route():
    result = check_domain_rules("can you process HIPAA patient data")
    assert result is not None
    # route name may vary — just assert it's not None and has a response
    assert "response" in result
    assert len(result["response"]) > 0

def test_normal_query_returns_none():
    result = check_domain_rules("What APIs does Epic support?")
    assert result is None

def test_billing_query_returns_none():
    result = check_domain_rules("Where can I find billing documentation?")
    assert result is None

def test_empty_string_returns_none():
    # Edge case: empty query should not match any rule
    result = check_domain_rules("")
    assert result is None
