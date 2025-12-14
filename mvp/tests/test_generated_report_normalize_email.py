import importlib


def test_normalize_email():
    module = importlib.import_module('src.tools_generated.report_normalize_email')
    payload = {"email": "JEFF@Example.COM ", "kind": "normalize_email"}
    out = module.run(payload)
    assert isinstance(out, dict)
    assert out.get('normalized_email') == 'jeff@example.com'
    assert out.get('final_answer') == 'Normalized email: jeff@example.com'
