import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from agent.coder import build_sql_request, plan_to_sql
from agent.llm_client import LLMClient
from semantic.semantic_layer import load_mapping as actual_load_mapping # Import actual function to call it in mock

# Define paths to dummy files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SEMANTIC_MAPPING_PATH = FIXTURES_DIR / "semantic_mapping.json"
SQL_SCHEMA_PATH = FIXTURES_DIR / "agent" / "sql_schema.json"

@pytest.fixture
def mock_semantic_layer_files(monkeypatch):
    """
    Mocks the file reading for semantic mapping and schemas to use dummy files.
    Pre-reads content to avoid recursion.
    """
    semantic_mapping_content = SEMANTIC_MAPPING_PATH.read_text(encoding="utf-8")
    sql_schema_content = SQL_SCHEMA_PATH.read_text(encoding="utf-8")

    def mock_read_text(self, encoding="utf-8"):
        if self == SEMANTIC_MAPPING_PATH:
            return semantic_mapping_content
        elif self == SQL_SCHEMA_PATH:
            return sql_schema_content
        raise FileNotFoundError(f"Mocked path not found: {self}")

    monkeypatch.setattr(Path, 'read_text', mock_read_text)
    
    # Also mock semantic_layer.load_mapping to ensure it gets the mocked content
    def mock_load_mapping(path: Path):
        if path == SEMANTIC_MAPPING_PATH:
            return json.loads(semantic_mapping_content)
        return actual_load_mapping(path) # Call the actual function for other paths
    
    monkeypatch.setattr("semantic.semantic_layer.load_mapping", mock_load_mapping)


@pytest.fixture
def mock_llm_client():
    """Provides a mocked LLMClient instance."""
    mock = MagicMock(spec=LLMClient)
    mock.chat = AsyncMock() # Make chat awaitable
    return mock


@pytest.fixture
def dummy_plan():
    return {
        "original_question": "테스트 테이블 1에서 값1을 보여줘",
        "intent": "SEARCH",
        "dataset": "test_table_1",
        "metrics": ["value1"],
        "filters": {"std_ymd": "20230101"},
        "group_by": [],
        "confidence": 0.95
    }

@pytest.fixture
def dummy_plan_with_joins():
    return {
        "original_question": "테스트 테이블 2와 연관된 값2를 보여줘",
        "intent": "SEARCH",
        "dataset": "test_table_2",
        "metrics": ["value2"],
        "filters": {"hcode": "12345"},
        "group_by": [],
        "confidence": 0.95
    }

def test_build_sql_request(mock_semantic_layer_files, dummy_plan):
    request_payload = build_sql_request(dummy_plan, SEMANTIC_MAPPING_PATH, SQL_SCHEMA_PATH)
    user_message_content = request_payload["messages"][1]["content"]

    assert "You are an NLQ SQL planner. Build a read-only SELECT query." in request_payload["messages"][0]["content"]
    assert "Original question: 테스트 테이블 1에서 값1을 보여줘" in user_message_content
    assert "Dataset: test_table_1" in user_message_content
    assert "Columns: std_ymd, value1" in user_message_content # From dummy semantic mapping
    assert "Plan JSON:" in user_message_content
    assert json.dumps(dummy_plan, ensure_ascii=True) in user_message_content
    assert "Schema:\n" in user_message_content
    assert json.loads(SQL_SCHEMA_PATH.read_text()) == json.loads(user_message_content.split("Schema:\n")[1])

def test_build_sql_request_with_constraints_and_joins(mock_semantic_layer_files):
    # This plan uses a dataset that has joins and constraints in dummy_semantic_mapping.json
    plan = {
        "original_question": "place_codes에서 20230101의 유효한 지역 코드를 보여줘",
        "intent": "SEARCH",
        "dataset": "place_codes", # This is defined in the dummy semantic mapping
        "metrics": ["code", "name"],
        "filters": {"std_ymd": "20230101"}, # This filter triggers the constraint hint
        "group_by": [],
        "confidence": 0.98
    }
    request_payload = build_sql_request(plan, SEMANTIC_MAPPING_PATH, SQL_SCHEMA_PATH)
    user_message_content = request_payload["messages"][1]["content"]

    assert "Dataset: place_codes" in user_message_content
    assert "Columns: code, name, sgng_cd, admin_code, sido_name, sigungu_name, eupmyeondong_name, dongri_name, created_at, abolished_at" in user_message_content
    assert "Constraints:\n- place_codes.created_at IS NULL OR place_codes.created_at <= '20230101'" in user_message_content
    assert "place_codes.abolished_at IS NULL OR place_codes.abolished_at >= '20230101'" in user_message_content


@pytest.mark.asyncio
async def test_plan_to_sql(mock_llm_client: MagicMock, mock_semantic_layer_files, dummy_plan):
    mock_sql = "SELECT std_ymd, value1 FROM test_table_1 WHERE std_ymd = '20230101';"
    mock_llm_client.chat.return_value = (
        f'```json\n{{"sql": "{mock_sql}", "notes": "Generated successfully"}}\n```',
        {"llm_request": "payload"},
        {"llm_response": "data"}
    )

    sql_payload, debug_payload = await plan_to_sql(
        dummy_plan,
        SEMANTIC_MAPPING_PATH,
        SQL_SCHEMA_PATH,
        mock_llm_client,
        debug=True
    )

    assert sql_payload["sql"] == mock_sql
    assert sql_payload["notes"] == "Generated successfully"
    assert debug_payload["llm_request"] == {"llm_request": "payload"}
    assert debug_payload["llm_response"] == {"llm_response": "data"}
    mock_llm_client.chat.assert_called_once()

@pytest.mark.asyncio
async def test_plan_to_sql_error(mock_llm_client: MagicMock, mock_semantic_layer_files, dummy_plan):
    mock_llm_client.chat.return_value = (
        'Invalid JSON response from LLM', # Malformed LLM response
        {"llm_request": "payload"},
        {"llm_response": "data"}
    )

    sql_payload, debug_payload = await plan_to_sql(
        dummy_plan,
        SEMANTIC_MAPPING_PATH,
        SQL_SCHEMA_PATH,
        mock_llm_client,
        debug=True
    )
    
    assert sql_payload["sql"] == ""
    assert "Failed to generate SQL." in sql_payload["notes"] or "JSON parse error" in sql_payload["notes"] or "No JSON object found." in sql_payload["notes"]
    assert debug_payload["llm_raw"] == "Invalid JSON response from LLM" # Check raw content when debug=True
