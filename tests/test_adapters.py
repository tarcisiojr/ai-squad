"""Testes para implementações de AIAgentAdapter."""

from unittest.mock import AsyncMock, patch

import pytest

from src.adapters.claude_agent_sdk import ClaudeAgentSDKAdapter
from src.adapters.interface import AIAgentAdapter
from src.models import AgentStatus


class TestClaudeAgentSDKAdapter:
    """Testes para ClaudeAgentSDKAdapter."""

    @pytest.fixture
    def adapter(self):
        """Cria instância de ClaudeAgentSDKAdapter."""
        return ClaudeAgentSDKAdapter(timeout=30)

    def test_herda_ai_agent_adapter(self, adapter):
        """Verifica que ClaudeAgentSDKAdapter implementa AIAgentAdapter."""
        assert isinstance(adapter, AIAgentAdapter)

    def test_status_inicial_idle(self, adapter):
        """Verifica que status inicial é IDLE."""
        assert adapter.status() == AgentStatus.IDLE

    def test_on_human_needed_registra_callback(self, adapter):
        """Verifica registro de callback para intervenção humana."""
        callback = AsyncMock()
        adapter.on_human_needed(callback)
        assert adapter._human_needed_callback is callback

    @pytest.mark.asyncio
    async def test_request_human_approval_com_callback(self, adapter):
        """Verifica solicitação de aprovação humana."""
        callback = AsyncMock(return_value="aprovado")
        adapter.on_human_needed(callback)

        resultado = await adapter.request_human_approval("Aprovar PR?")

        assert resultado == "aprovado"
        callback.assert_called_once_with("Aprovar PR?")
        assert adapter.status() == AgentStatus.RUNNING

    @pytest.mark.asyncio
    async def test_request_human_approval_sem_callback(self, adapter):
        """Verifica erro quando não há callback registrado."""
        with pytest.raises(RuntimeError, match="Nenhum callback"):
            await adapter.request_human_approval("Aprovar?")

    def test_timeout_configuravel(self):
        """Verifica que timeout é configurável."""
        adapter = ClaudeAgentSDKAdapter(timeout=600)
        assert adapter._timeout == 600

    def test_working_dir_configuravel(self):
        """Verifica que working_dir é configurável."""
        adapter = ClaudeAgentSDKAdapter(working_dir="/tmp/projeto")
        assert adapter._working_dir == "/tmp/projeto"

    def test_model_configuravel(self):
        """Verifica que model é configurável."""
        adapter = ClaudeAgentSDKAdapter(model="claude-sonnet-4-20250514")
        assert adapter._model == "claude-sonnet-4-20250514"

    def test_build_prompt_com_contexto(self, adapter):
        """Verifica montagem do prompt com contexto."""
        prompt = adapter._build_prompt(
            "Crie um teste", {"linguagem": "python", "framework": "pytest"}
        )
        assert "## Contexto" in prompt
        assert "linguagem: python" in prompt
        assert "Crie um teste" in prompt

    def test_build_prompt_sem_contexto(self, adapter):
        """Verifica montagem do prompt sem contexto."""
        prompt = adapter._build_prompt("Crie um teste", {})
        assert "Crie um teste" in prompt

    def test_build_prompt_com_product_context(self, adapter):
        """Verifica montagem do prompt com contexto do produto."""
        prompt = adapter._build_prompt(
            "Crie um teste",
            {"product_context": "README conteudo aqui"},
        )
        assert "## Contexto do Projeto" in prompt
        assert "README conteudo aqui" in prompt

    def test_build_prompt_com_system_instructions(self, adapter):
        """Verifica montagem do prompt com instruções do sistema."""
        prompt = adapter._build_prompt(
            "Crie um teste",
            {"system_instructions": "Voce e o PO."},
        )
        assert "Voce e o PO." in prompt

    def test_set_callbacks(self, adapter):
        """Verifica que callbacks são configuráveis."""
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        cb3 = AsyncMock()
        cb4 = AsyncMock()

        adapter.set_progress_callback(cb1)
        adapter.set_start_agent_callback(cb2)
        adapter.set_get_agents_callback(cb3)
        adapter.set_check_artifacts_callback(cb4)

        assert adapter._progress_callback is cb1
        assert adapter._start_agent_callback is cb2
        assert adapter._get_agents_callback is cb3
        assert adapter._check_artifacts_callback is cb4

    def test_session_management(self, adapter):
        """Verifica gerenciamento de sessões."""
        assert adapter.get_session_id("conv-1") is None

        adapter._sessions["conv-1"] = "session-abc"
        assert adapter.get_session_id("conv-1") == "session-abc"

        adapter.clear_session("conv-1")
        assert adapter.get_session_id("conv-1") is None

    def test_mcp_server_criado(self, adapter):
        """Verifica que MCP server é criado com tools."""
        assert adapter._mcp_server is not None
