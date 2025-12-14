import importlib


def test_normalize_sample_payload():
    mod = importlib.import_module('src.tools_generated.normalize_email_tool')
    payload = {"email": "JEFF@Example.COM ", "kind": "normalize_email"}
    out = mod.run(payload)
    assert isinstance(out, dict)
    assert 'final_answer' in out
    assert out['final_answer'] == 'jeff@example.com'
    # convenience field should match
    assert out.get('normalized_email') == 'jeff@example.com'
