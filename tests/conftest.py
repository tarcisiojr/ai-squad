"""Fixtures compartilhadas para todos os testes."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from click.testing import CliRunner

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.models import AgentStatus


class MockAdapter(AIAgentAdapter):
    """Mock do AIAgentAdapter para testes."""

    def __init__(self):
        self._status = AgentStatus.IDLE
        self._callback = None
        self._run_mock = AsyncMock(return_value="resultado mock")
        self._ask_mock = AsyncMock(return_value="resposta mock")

    async def run(self, prompt: str, context: str = "") -> str:
        return await self._run_mock(prompt, context)

    async def ask(self, question: str) -> str:
        return await self._ask_mock(question)

    def status(self) -> AgentStatus:
        return self._status

    def on_human_needed(self, callback):
        self._callback = callback


class MockMessageBus:
    """Mock do MessageBus para testes."""

    def __init__(self):
        self.send_message = AsyncMock()
        self.send_photo = AsyncMock()
        self.send_approval_request = AsyncMock(return_value="aprovado")
        self.ask_user = AsyncMock(return_value="resposta do usuário")
        self.send_typing = AsyncMock()
        self.notify = AsyncMock()


@pytest.fixture
def runner():
    """Cria CliRunner para testes de CLI."""
    return CliRunner()


@pytest.fixture
def mock_adapter():
    """Cria MockAdapter para testes."""
    return MockAdapter()


@pytest.fixture
def mock_bus():
    """Cria MockMessageBus para testes."""
    return MockMessageBus()


@pytest.fixture
def mock_platform_config(tmp_path):
    """Cria PlatformConfig mock com diretório temporário."""
    config = MagicMock()
    config.ai_provider = "claude-agent-sdk"
    config.messaging_provider = "telegram"
    config.ai_model = "claude-sonnet-4-20250514"
    config.agent_timeout = 300
    config.team_dir = str(tmp_path)
    config.state_dir = str(tmp_path / "state")
    return config
