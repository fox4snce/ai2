import pytest

from src.tools_generated.normalize_phone import run


def test_normalize_phone_us_basic():
    inputs = { 'kind': 'normalize_phone', 'phone': ' (555) 123-4567 ' }
    out = run(inputs)
    assert isinstance(out, dict)
    assert out.get('normalized') == '+15551234567'
    assert 'final_answer' in out and '+15551234567' in out['final_answer']


def test_normalize_phone_with_plus():
    inputs = { 'kind': 'normalize_phone', 'phone': '+44 20 7946 0958' }
    out = run(inputs)
    assert out.get('normalized') == '+442079460958'


def test_normalize_phone_empty():
    inputs = { 'kind': 'normalize_phone', 'phone': '   ' }
    out = run(inputs)
    assert out.get('normalized') == ''
