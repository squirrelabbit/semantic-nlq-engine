import pytest
from agent.llm_parser import extract_json

def test_extract_json():
    # Scenario 1: Valid JSON
    content = '{"key": "value", "number": 123}'
    parsed, error = extract_json(content)
    assert parsed == {"key": "value", "number": 123}
    assert error is None

    # Scenario 2: JSON with markdown fences
    content = '```json\n{"key": "value2", "boolean": true}\n```'
    parsed, error = extract_json(content)
    assert parsed == {"key": "value2", "boolean": True}
    assert error is None

    # Scenario 3: JSON with extra text before and after
    content = 'Some leading text.```json\n{"key": "value3"}\n```Trailing text.'
    parsed, error = extract_json(content)
    assert parsed == {"key": "value3"}
    assert error is None

    # Scenario 4: JSON with text only before
    content = 'Leading text.\n{"key": "value4"}'
    parsed, error = extract_json(content)
    assert parsed == {"key": "value4"}
    assert error is None

    # Scenario 5: JSON with text only after
    content = '{"key": "value5"}\nTrailing text.'
    parsed, error = extract_json(content)
    assert parsed == {"key": "value5"}
    assert error is None

    # Scenario 6: Empty string
    content = ''
    parsed, error = extract_json(content)
    assert parsed == {}
    assert error == "No JSON object found." # Explicitly assert the exact error string

    # Scenario 7: Invalid JSON
    content = '{"key": "value", "number":}'
    parsed, error = extract_json(content)
    assert parsed == {}
    assert "JSON parse error" in error

    # Scenario 8: No JSON object found
    content = 'This is not json.'
    parsed, error = extract_json(content)
    assert parsed == {}
    assert error == "No JSON object found." # Explicitly assert the exact error string

    # Scenario 9: None input
    content = None
    parsed, error = extract_json(content)
    assert parsed == {}
    assert error == "Empty LLM response." # Explicitly assert the exact error string

    # Scenario 10: Multiple JSON objects (results in JSONDecodeError)
    content = '{"outer": "first", "inner": {"key": "value"}}, {"another": "object"}'
    parsed, error = extract_json(content)
    assert parsed == {}
    assert "JSON parse error" in error

    # Scenario 11: JSON object with nested structures and arrays
    content = '{"data": {"items": [1, 2, {"id": 3}]}, "status": "success"}'
    parsed, error = extract_json(content)
    assert parsed == {"data": {"items": [1, 2, {"id": 3}]}, "status": "success"}
    assert error is None
