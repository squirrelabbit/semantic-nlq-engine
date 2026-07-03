import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from agent.planner import build_plan_request, plan_question, plan_question_two_stage
from agent.llm_client import LLMClient
from semantic.prompt_builder import build_l1_context, build_l2_context
from semantic.semantic_layer import load_mapping as actual_load_mapping # Import actual function to call it in mock

# Define paths to dummy files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SEMANTIC_MAPPING_PATH = FIXTURES_DIR / "semantic_mapping.json"
PLAN_SCHEMA_PATH = FIXTURES_DIR / "agent" / "plan_schema.json"
PLAN_L1_SCHEMA_PATH = FIXTURES_DIR / "agent" / "plan_l1_schema.json"

@pytest.fixture
def mock_semantic_layer_files(monkeypatch):
    """
    Mocks the file reading for semantic mapping and schemas to use dummy files.
    Pre-reads content to avoid recursion.
    """
    semantic_mapping_content = SEMANTIC_MAPPING_PATH.read_text(encoding="utf-8")
    plan_schema_content = PLAN_SCHEMA_PATH.read_text(encoding="utf-8")
    plan_l1_schema_content = PLAN_L1_SCHEMA_PATH.read_text(encoding="utf-8")

    def mock_read_text(self, encoding="utf-8"):
        if self == SEMANTIC_MAPPING_PATH:
            return semantic_mapping_content
        elif self == PLAN_SCHEMA_PATH:
            return plan_schema_content
        elif self == PLAN_L1_SCHEMA_PATH:
            return plan_l1_schema_content
        # Fallback for other Path.read_text calls if needed, or raise an error
        raise FileNotFoundError(f"Mocked path not found: {self}")

    monkeypatch.setattr(Path, 'read_text', mock_read_text)
    
    # Also mock semantic_layer.load_mapping to ensure it gets the mocked content
    def mock_load_mapping(path: Path):
        if path == SEMANTIC_MAPPING_PATH:
            return json.loads(semantic_mapping_content)
        return actual_load_mapping(path) # Call the actual function for other paths
    
    monkeypatch.setattr("semantic.semantic_layer.load_mapping", mock_load_mapping)


@pytest.fixture
def dummy_semantic_mapping_content():
    """Provides the raw content of the dummy semantic mapping."""
    return SEMANTIC_MAPPING_PATH.read_text(encoding="utf-8")

@pytest.fixture
def dummy_semantic_mapping():
    """Provides the parsed content of the dummy semantic mapping."""
    return json.loads(SEMANTIC_MAPPING_PATH.read_text(encoding="utf-8"))


def extract_context_from_message(message_content: str) -> str:
    """Helper to extract the context part from the user message content."""
    # Context ends before "Current_Date:" or "Schema:"
    if "\n\nCurrent_Date:" in message_content:
        return message_content.split("\n\nCurrent_Date:")[0].strip()
    if "\n\nSchema:" in message_content:
        return message_content.split("\n\nSchema:")[0].strip()
    return message_content.strip()


def test_build_plan_request_l1_context(mock_semantic_layer_files, dummy_semantic_mapping):
    question = "인구 데이터에 대해 알려줘"
    request = build_plan_request(question, SEMANTIC_MAPPING_PATH, PLAN_L1_SCHEMA_PATH, selected_tables=None)
    user_message_content = request["messages"][1]["content"]
    
    expected_l1_context_from_builder = build_l1_context(dummy_semantic_mapping)
    assert expected_l1_context_from_builder in user_message_content

    assert "You are an NLQ planner. Select 2-3 candidate datasets to answer the question" in request["messages"][0]["content"]
    assert "Schema:\n" in user_message_content
    assert json.loads(PLAN_L1_SCHEMA_PATH.read_text()) == json.loads(user_message_content.split("Schema:\n")[1])


def test_build_plan_request_l2_context(mock_semantic_layer_files, dummy_semantic_mapping):
    question = "테스트 테이블 1에서 값1을 보여줘"
    selected_tables = ["test_table_1"]
    request = build_plan_request(question, SEMANTIC_MAPPING_PATH, PLAN_SCHEMA_PATH, selected_tables=selected_tables)
    user_message_content = request["messages"][1]["content"]

    expected_l2_context_from_builder = build_l2_context(dummy_semantic_mapping, selected_tables)
    assert expected_l2_context_from_builder in user_message_content

    assert "You are an NLQ planner. Choose exactly one dataset from the candidates and finalize the plan." in request["messages"][0]["content"]
    assert "Schema:\n" in user_message_content
    assert json.loads(PLAN_SCHEMA_PATH.read_text()) == json.loads(user_message_content.split("Schema:\n")[1])


@pytest.mark.asyncio
async def test_plan_question(mock_llm_client: MagicMock, mock_semantic_layer_files):
    question = "테스트 테이블 1에서 값1을 보여줘"
    mock_llm_client.chat.return_value = ( # This is now an awaitable from AsyncMock
        '```json\n{\"intent\": \"SEARCH\", \"dataset\": \"test_table_1\", \"metrics\": [\"value1\"], \"filters\": {}, \"confidence\": 0.9}\n```',
        {"llm_request": "payload"},
        {"llm_response": "data"}
    )
    
    plan, debug_payload = await plan_question(
        question,
        SEMANTIC_MAPPING_PATH,
        PLAN_SCHEMA_PATH,
        mock_llm_client,
        debug=True
    )

    assert plan["dataset"] == "test_table_1"
    assert plan["metrics"] == ["value1"]
    assert plan["original_question"] == question
    assert debug_payload["llm_request"] == {"llm_request": "payload"}
    assert debug_payload["llm_response"] == {"llm_response": "data"}
    mock_llm_client.chat.assert_called_once() # Ensure it's called once

@pytest.mark.asyncio
async def test_plan_question_two_stage(mock_llm_client: MagicMock, mock_semantic_layer_files):
    question = "두 번째 테이블 데이터에서 hcode를 보여줘"

    # Configure side_effect for the AsyncMock
    mock_llm_client.chat.side_effect = [
        ( # First call (L1) - tuple directly
            '```json\n{\"original_question\": \"두 번째 테이블 데이터에서 hcode를 보여줘\", \"datasets\": [\"test_table_2\"], \"confidence\": 0.95}\n```',
            {"l1_request": "payload"},
            {"l1_response": "data"}
        ),
        ( # Second call (L2) - tuple directly
            '```json\n{\"intent\": \"SEARCH\", \"dataset\": \"test_table_2\", \"metrics\": [\"value2\"], \"filters\": {\"hcode\": \"abc\"}, \"confidence\": 0.99}\n```',
            {"l2_request": "payload"},
            {"l2_response": "data"}
        )
    ]

    plan, debug_payload = await plan_question_two_stage(
        question,
        SEMANTIC_MAPPING_PATH,
        PLAN_L1_SCHEMA_PATH,
        PLAN_SCHEMA_PATH,
        mock_llm_client,
        debug=True
    )

    assert plan["dataset"] == "test_table_2"
    assert plan["filters"] == {"hcode": "abc"}
    assert plan["original_question"] == question
    assert "l1_request" in debug_payload
    assert "l2_request" in debug_payload
    assert mock_llm_client.chat.call_count == 2
    
    # Check the content of the last call arguments
    last_call_args = mock_llm_client.chat.call_args_list[1][0][0] # messages arg of the second call
    expected_l2_messages_payload = build_plan_request(question, SEMANTIC_MAPPING_PATH, PLAN_SCHEMA_PATH, selected_tables=["test_table_2"])
    expected_l2_messages = expected_l2_messages_payload["messages"]
    
    assert last_call_args[0]["role"] == expected_l2_messages[0]["role"]
    assert "You are an NLQ planner. Choose exactly one dataset" in last_call_args[0]["content"]

    assert last_call_args[1]["role"] == expected_l2_messages[1]["role"]
    assert "Allowed datasets (L2 detail):" in last_call_args[1]["content"]
    assert "Question: 두 번째 테이블 데이터에서 hcode를 보여줘" in last_call_args[1]["content"]
    assert "Schema:" in last_call_args[1]["content"]
