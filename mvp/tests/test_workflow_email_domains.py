import json

from src.main import MVPAPI


def _tool_names(trace: dict) -> list[str]:
    return [tr.get("tool_name") for tr in trace.get("tool_runs", []) or [] if tr.get("tool_name")]


def test_workflow_email_domains_branches_to_clarify_when_no_emails_found():
    obligations = json.loads(open("schemas/obligations.workflow_email_domains_clarify.json", "r", encoding="utf-8-sig").read())
    api = MVPAPI(":memory:")
    try:
        trace = api.execute_obligations(obligations)
    finally:
        api.close()

    assert trace.get("status") == "clarify"
    assert "text" in (trace.get("clarify") or [])

    tools = _tool_names(trace)
    assert "Reasoning.Core" in tools
    # extractor ran, but pipeline stopped before normalize/count
    assert "EmailOps.Extract" in tools or "EmailOps.ExtractStrict" in tools
    assert "Normalize.EmailsBatch" not in tools
    assert "EmailOps.CountDistinctDomains" not in tools


def test_workflow_email_domains_propagates_denylist_domains():
    obligations = json.loads(open("schemas/obligations.workflow_email_domains_denylist.json", "r", encoding="utf-8-sig").read())
    api = MVPAPI(":memory:")
    try:
        trace = api.execute_obligations(obligations)
    finally:
        api.close()

    assert trace.get("status") == "resolved"
    tools = _tool_names(trace)
    assert "Normalize.EmailsBatch" in tools
    assert "EmailOps.CountDistinctDomains" in tools

    # Find the domain counter run and verify denylist is present and respected.
    dom_run = next(tr for tr in trace.get("tool_runs", []) if tr.get("tool_name") == "EmailOps.CountDistinctDomains")
    assert dom_run["inputs"]["denylist_domains"] == ["example.com"]
    assert dom_run["outputs"]["distinct_domains"] == ["other.org"]
    assert dom_run["outputs"]["distinct_domain_count"] == 1


def test_workflow_email_domains_chooses_strict_extractor_when_constrained():
    obligations = json.loads(
        open("schemas/obligations.workflow_email_domains_constraints_strict.json", "r", encoding="utf-8-sig").read()
    )
    api = MVPAPI(":memory:")
    try:
        trace = api.execute_obligations(obligations)
    finally:
        api.close()

    assert trace.get("status") == "resolved"
    tools = _tool_names(trace)
    assert "EmailOps.ExtractStrict" in tools


