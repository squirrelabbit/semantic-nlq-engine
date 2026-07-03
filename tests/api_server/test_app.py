import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from api_server.app import app, get_db_conn
import api_server.app as app_module # Import the app module to patch its variables
import psycopg
from psycopg.rows import dict_row
from datetime import datetime
from pathlib import Path

# Mock the run_nlq_workflow from agent.core
@pytest.fixture
def mock_run_nlq_workflow():
    with patch("api_server.app.run_nlq_workflow") as mock:
        yield mock

# Mock the get_db_conn to return a mock connection and cursor
@pytest.fixture
def mock_db_connection():
    with patch("api_server.app.get_db_conn") as mock_get_db_conn:
        mock_conn = MagicMock(spec=psycopg.Connection)
        mock_cursor = MagicMock(spec=psycopg.Cursor)
        mock_cursor.row_factory = dict_row # Ensure dict_row is set for cursor

        # Configure connection to return a context manager for cursor
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = None
        
        # Configure connection to be a context manager itself
        mock_get_db_conn.return_value.__enter__.return_value = mock_conn
        mock_get_db_conn.return_value.__exit__.return_value = None
        
        yield mock_conn, mock_cursor

@pytest.fixture
def mock_app_repo_root(monkeypatch):
    """Mocks the repo_root variable in api_server.app."""
    mock_path = Path("/mock/project/root")
    monkeypatch.setattr(app_module, "repo_root", mock_path)
    return mock_path

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_nlq_success(mock_run_nlq_workflow, mock_app_repo_root): # Add mock_app_repo_root fixture
    # Configure the mock workflow to return a successful result
    mock_run_nlq_workflow.return_value = {
        "plan": {"intent": "SEARCH"},
        "sql": "SELECT * FROM test;",
        "rows": [{"col1": "val1"}],
        "insight": {"summary": "test summary"},
        "request_id": "test-req-id"
    }

    response = client.post(
        "/api/nlq",
        json={"question": "test question", "two_stage": True, "execute": True, "interpret": True}
    )

    assert response.status_code == 200
    assert response.json()["plan"]["intent"] == "SEARCH"
    assert response.json()["sql"] == "SELECT * FROM test;"
    assert response.json()["rows"] == [{"col1": "val1"}]
    assert response.json()["insight"]["summary"] == "test summary"
    assert response.json()["request_id"] == "test-req-id"
    
    mock_run_nlq_workflow.assert_called_once_with(
        question="test question",
        two_stage=True,
        execute=True,
        interpret=True,
        direct=True,
        repo_root=mock_app_repo_root # Use the mocked repo_root
    )

@pytest.mark.asyncio
async def test_nlq_failure(mock_run_nlq_workflow, mock_app_repo_root): # Add mock_app_repo_root fixture
    # Configure the mock workflow to raise an exception
    mock_run_nlq_workflow.side_effect = ValueError("Workflow failed")

    response = client.post(
        "/api/nlq",
        json={"question": "failing question"}
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Workflow failed"
    mock_run_nlq_workflow.assert_called_once()


# --- Knowledge Card CRUD Tests ---
@pytest.mark.asyncio
async def test_create_knowledge_card(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = {
        "id": 1,
        "title": "Test Card",
        "summary": "Summary of Test Card",
        "tags": ["tag1"],
        "sources": ["source1"],
        "created_at": datetime(2023, 1, 1)
    }

    response = client.post(
        "/api/knowledge_cards",
        json={
            "title": "Test Card",
            "summary": "Summary of Test Card",
            "tags": ["tag1"],
            "sources": ["source1"]
        }
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Test Card"
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

@pytest.mark.asyncio
async def test_list_knowledge_cards(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchall.return_value = [
        {
            "id": 1,
            "title": "Card 1",
            "summary": "Summary 1",
            "tags": [],
            "sources": [],
            "created_at": datetime(2023, 1, 1)
        },
        {
            "id": 2,
            "title": "Card 2",
            "summary": "Summary 2",
            "tags": ["tag2"],
            "sources": ["src2"],
            "created_at": datetime(2023, 1, 2)
        }
    ]

    response = client.get("/api/knowledge_cards")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["title"] == "Card 1"
    mock_cursor.execute.assert_called_once()

@pytest.mark.asyncio
async def test_get_knowledge_card(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = {
        "id": 1,
        "title": "Specific Card",
        "summary": "Specific Summary",
        "tags": ["specific"],
        "sources": ["specific_source"],
        "created_at": datetime(2023, 1, 1)
    }

    response = client.get("/api/knowledge_cards/1")
    assert response.status_code == 200
    assert response.json()["title"] == "Specific Card"
    mock_cursor.execute.assert_called_once_with(
        "SELECT id, title, summary, tags, sources, created_at FROM knowledge_cards WHERE id = %s", (1,)
    )

@pytest.mark.asyncio
async def test_get_knowledge_card_not_found(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = None

    response = client.get("/api/knowledge_cards/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Knowledge card not found."
    mock_cursor.execute.assert_called_once()

@pytest.mark.asyncio
async def test_update_knowledge_card(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = {
        "id": 1,
        "title": "Updated Card",
        "summary": "Updated Summary",
        "tags": ["updated_tag"],
        "sources": ["updated_source"],
        "created_at": datetime(2023, 1, 1) # created_at doesn't change on update
    }

    response = client.put(
        "/api/knowledge_cards/1",
        json={
            "title": "Updated Card",
            "summary": "Updated Summary",
            "tags": ["updated_tag"],
            "sources": ["updated_source"]
        }
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Card"
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

@pytest.mark.asyncio
async def test_delete_knowledge_card(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.rowcount = 1 # Simulate one row affected by delete

    response = client.delete("/api/knowledge_cards/1")
    assert response.status_code == 204
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

@pytest.mark.asyncio
async def test_delete_knowledge_card_not_found(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.rowcount = 0 # Simulate no rows affected

    response = client.delete("/api/knowledge_cards/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Knowledge card not found."
    mock_cursor.execute.assert_called_once()


# --- Semantic Metadata CRUD Tests ---
@pytest.mark.asyncio
async def test_create_semantic_metadata(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = {
        "id": 1,
        "target_table": "new_table",
        "business_name": "New Table Name",
        "semantic_desc": "Desc",
        "join_rules": {},
        "allowed_metrics": [],
        "constraints": [],
        "samples": {},
        "updated_at": datetime(2023, 1, 1)
    }

    response = client.post(
        "/api/semantic_metadata",
        json={
            "target_table": "new_table",
            "business_name": "New Table Name"
        }
    )

    assert response.status_code == 201
    assert response.json()["target_table"] == "new_table"
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

@pytest.mark.asyncio
async def test_create_semantic_metadata_conflict(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    # Simulate ON CONFLICT DO NOTHING returning nothing
    mock_cursor.fetchone.return_value = None 

    response = client.post(
        "/api/semantic_metadata",
        json={
            "target_table": "existing_table",
            "business_name": "Existing Table"
        }
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Semantic metadata for table 'existing_table' already exists."
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()


@pytest.mark.asyncio
async def test_list_semantic_metadata(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchall.return_value = [
        {
            "id": 1,
            "target_table": "table1",
            "business_name": "Table One",
            "semantic_desc": None,
            "join_rules": {},
            "allowed_metrics": [],
            "constraints": [],
            "samples": {},
            "updated_at": datetime(2023, 1, 1)
        },
        {
            "id": 2,
            "target_table": "table2",
            "business_name": "Table Two",
            "semantic_desc": "Another table",
            "join_rules": {},
            "allowed_metrics": ["count"],
            "constraints": [],
            "samples": {},
            "updated_at": datetime(2023, 1, 2)
        }
    ]

    response = client.get("/api/semantic_metadata")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["target_table"] == "table1"
    mock_cursor.execute.assert_called_once()

@pytest.mark.asyncio
async def test_get_semantic_metadata(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = {
        "id": 1,
        "target_table": "specific_table",
        "business_name": "Specific Table Name",
        "semantic_desc": None,
        "join_rules": {},
        "allowed_metrics": [],
        "constraints": [],
        "samples": {},
        "updated_at": datetime(2023, 1, 1)
    }

    response = client.get("/api/semantic_metadata/1")
    assert response.status_code == 200
    assert response.json()["target_table"] == "specific_table"
    mock_cursor.execute.assert_called_once_with(
        """
                SELECT id, target_table, business_name, semantic_desc, join_rules, allowed_metrics, constraints, samples, updated_at
                FROM semantic_metadata WHERE id = %s
            """, (1,)
    )

@pytest.mark.asyncio
async def test_get_semantic_metadata_not_found(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = None

    response = client.get("/api/semantic_metadata/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Semantic metadata not found."
    mock_cursor.execute.assert_called_once()

@pytest.mark.asyncio
async def test_update_semantic_metadata(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = {
        "id": 1,
        "target_table": "updated_table",
        "business_name": "Updated Table Name",
        "semantic_desc": "Updated Desc",
        "join_rules": {"key": "value"},
        "allowed_metrics": ["sum"],
        "constraints": ["c1"],
        "samples": {"col": "val"},
        "updated_at": datetime(2023, 1, 2) # updated_at should change
    }

    response = client.put(
        "/api/semantic_metadata/1",
        json={
            "target_table": "updated_table",
            "business_name": "Updated Table Name",
            "semantic_desc": "Updated Desc",
            "join_rules": {"key": "value"},
            "allowed_metrics": ["sum"],
            "constraints": ["c1"],
            "samples": {"col": "val"}
        }
    )

    assert response.status_code == 200
    assert response.json()["target_table"] == "updated_table"
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

@pytest.mark.asyncio
async def test_delete_semantic_metadata(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.rowcount = 1 # Simulate one row affected by delete

    response = client.delete("/api/semantic_metadata/1")
    assert response.status_code == 204
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

@pytest.mark.asyncio
async def test_delete_semantic_metadata_not_found(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.rowcount = 0 # Simulate no rows affected

    response = client.delete("/api/semantic_metadata/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Semantic metadata not found."
    mock_cursor.execute.assert_called_once()