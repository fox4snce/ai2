import importlib


def test_normalize_basic():
    mod = importlib.import_module('src.tools_generated.report_normalize_url')
    res = mod.run({'url': 'www.bob.com'})
    assert isinstance(res, dict)
    assert res.get('normalized_url') == 'https://www.bob.com'
    assert 'Normalized URL: https://www.bob.com' in res.get('final_answer', '')


def test_normalize_with_query_and_case():
    mod = importlib.import_module('src.tools_generated.report_normalize_url')
    res = mod.run({'url': 'HTTP://Example.COM:80/a/b/?b=2&a=1#frag'})
    # scheme http with port 80 is default and should be preserved as http if provided scheme was http
    # but default ports should be removed; we expect scheme lowercased, host lowercased, sorted query
    assert res.get('normalized_url') == 'http://example.com/a/b?a=1&b=2'
    assert 'Normalized URL: http://example.com/a/b?a=1&b=2' in res.get('final_answer', '')
