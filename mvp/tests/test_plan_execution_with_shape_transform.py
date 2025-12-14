import json

from src.main import MVPAPI


def _tool_run(trace: dict, name: str) -> dict | None:
    for tr in trace.get("tool_runs", []) or []:
        if tr.get("tool_name") == name:
            return tr
    return None


def test_shape_transform_pipeline_emails_to_domains():
    """
    Data-dependent composition with shape transform:
      Step 1: extract emails -> outputs.emails (list)
      Step 2: normalize batch -> inputs.emails references STEP_1.emails (list)
      Step 3: count distinct domains -> inputs.emails references STEP_2.normalized_emails (list)

    Pass condition:
      - Trace proves $ref substitution occurred (step2/step3 tool_run inputs contain lists, not $ref dicts)
      - Final distinct domain count matches expected
    """
    obligations = json.loads(
        open("schemas/obligations.demo_chain_emails_batch_domains.json", "r", encoding="utf-8-sig").read()
    )

    api = MVPAPI(":memory:")
    try:
        trace = api.execute_obligations(obligations)
    finally:
        api.close()

    assert trace.get("status") == "resolved"

    ex = _tool_run(trace, "EmailOps.Extract")
    nb = _tool_run(trace, "Normalize.EmailsBatch")
    cd = _tool_run(trace, "EmailOps.CountDistinctDomains")
    assert ex and nb and cd

    extracted = (ex.get("outputs") or {}).get("emails")
    assert extracted == ["JEFF@Example.COM", "jeff+4@Other.org"]

    # Prove shape substitution: Normalize.EmailsBatch inputs.emails is the extracted list (not a "$ref" object).
    assert (nb.get("inputs") or {}).get("emails") == extracted
    normalized = (nb.get("outputs") or {}).get("normalized_emails")
    assert normalized == ["jeff@example.com", "jeff+4@other.org"]

    # Prove shape substitution: domain counter consumes normalized_emails list.
    assert (cd.get("inputs") or {}).get("emails") == normalized
    assert (cd.get("outputs") or {}).get("distinct_domain_count") == 2
    # Parent final_answer is a JSON list of each step's final_answer.
    step_answers = json.loads(trace.get("final_answer"))
    assert step_answers == [json.dumps(extracted), json.dumps(normalized), "2"]


