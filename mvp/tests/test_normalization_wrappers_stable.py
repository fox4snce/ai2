import json

from src.main import MVPAPI


def test_normalization_wrappers_outputs_stable():
    """
    Consolidation guardrail: wrappers must keep output shape stable forever.
    (Normalize library can evolve internally, but wrappers must not break obligations.)
    """
    api = MVPAPI(":memory:")
    try:
        # normalize_email
        t = api.execute_obligations(
            {"obligations": [{"type": "REPORT", "payload": {"kind": "normalize_email", "email": "JEFF@Example.COM "}}]}
        )
        assert t.get("final_answer") == "Normalized email: jeff@example.com"

        # normalize_url
        t = api.execute_obligations(
            {"obligations": [{"type": "REPORT", "payload": {"kind": "normalize_url", "url": "HTTP://Example.COM:80/a/b/?b=2&a=1#frag"}}]}
        )
        assert t.get("final_answer") == "Normalized URL: http://example.com/a/b?a=1&b=2"

        # normalize_phone
        t = api.execute_obligations(
            {"obligations": [{"type": "REPORT", "payload": {"kind": "normalize_phone", "phone": " (555) 123-4567 "}}]}
        )
        assert t.get("final_answer") == "normalized_phone: +15551234567"
    finally:
        api.close()


