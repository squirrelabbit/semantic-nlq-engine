import pytest
from unittest.mock import MagicMock, AsyncMock # Import AsyncMock
from agent.llm_client import LLMClient

@pytest.fixture
def mock_llm_client():
    """Provides a mocked LLMClient instance."""
    mock = MagicMock(spec=LLMClient)
    # Configure the chat method to be an AsyncMock
    mock.chat = AsyncMock() # Make chat awaitable
    return mock