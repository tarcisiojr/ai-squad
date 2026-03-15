"""Testes para o adapter Claude Agent SDK."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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

    @pytest.mark.asyncio
    async def test_run_sucesso(self, adapter):
        """Verifica execução com sucesso via SDK mock."""
        mock_text_block = MagicMock()
        mock_text_block.text = "Resultado do SDK"

        mock_message = MagicMock()
        mock_message.content = [mock_text_block]

        async def mock_query(**kwargs):
            yield mock_message

        with patch(
            "src.adapters.claude_agent_sdk.query", side_effect=mock_query
        ), patch(
            "src.adapters.claude_agent_sdk.AssistantMessage",
            type(mock_message),
        ), patch(
            "src.adapters.claude_agent_sdk.TextBlock",
            type(mock_text_block),
        ):
            resultado = await adapter.run(
                "Crie um hello world", {"lang": "python"}
            )

        assert resultado == "Resultado do SDK"
        assert adapter.status() == AgentStatus.DONE

    @pytest.mark.asyncio
    async def test_run_timeout(self, adapter):
        """Verifica tratamento de timeout."""

        async def mock_query_lento(**kwargs):
            await asyncio.sleep(10)
            yield MagicMock()  # pragma: no cover

        adapter._timeout = 0.01

        with patch(
            "src.adapters.claude_agent_sdk.query", side_effect=mock_query_lento
        ):
            with pytest.raises(TimeoutError, match="excedeu timeout"):
                await adapter.run("prompt longo", {})

        assert adapter.status() == AgentStatus.ERROR

    @pytest.mark.asyncio
    async def test_run_erro_sdk(self, adapter):
        """Verifica tratamento de erro genérico do SDK."""

        async def mock_query_erro(**kwargs):
            raise RuntimeError("Erro interno do SDK")
            yield  # pragma: no cover

        with patch(
            "src.adapters.claude_agent_sdk.query", side_effect=mock_query_erro
        ):
            with pytest.raises(RuntimeError, match="Erro no Claude Agent SDK"):
                await adapter.run("prompt", {})

        assert adapter.status() == AgentStatus.ERROR

    @pytest.mark.asyncio
    async def test_ask_delega_para_run(self, adapter):
        """Verifica que ask delega para run com contexto vazio."""
        mock_text_block = MagicMock()
        mock_text_block.text = "Resposta"

        mock_message = MagicMock()
        mock_message.content = [mock_text_block]

        async def mock_query(**kwargs):
            yield mock_message

        with patch(
            "src.adapters.claude_agent_sdk.query", side_effect=mock_query
        ), patch(
            "src.adapters.claude_agent_sdk.AssistantMessage",
            type(mock_message),
        ), patch(
            "src.adapters.claude_agent_sdk.TextBlock",
            type(mock_text_block),
        ):
            resultado = await adapter.ask("Qual é o sentido da vida?")

        assert resultado == "Resposta"

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

    def test_build_prompt_com_contexto(self, adapter):
        """Verifica montagem do prompt com contexto."""
        prompt = adapter._build_prompt(
            "Crie um teste", {"linguagem": "python", "framework": "pytest"}
        )
        assert "## Contexto" in prompt
        assert "linguagem: python" in prompt
        assert "## Tarefa" in prompt
        assert "Crie um teste" in prompt

    def test_build_prompt_sem_contexto(self, adapter):
        """Verifica montagem do prompt sem contexto."""
        prompt = adapter._build_prompt("Crie um teste", {})
        assert "## Contexto" not in prompt
        assert "## Tarefa" in prompt
        assert "Crie um teste" in prompt

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

    def test_model_padrao_none(self):
        """Verifica que model padrão é None."""
        adapter = ClaudeAgentSDKAdapter()
        assert adapter._model is None

    def test_build_options_com_model(self):
        """Verifica que opções incluem model quando configurado."""
        adapter = ClaudeAgentSDKAdapter(
            model="claude-sonnet-4-20250514",
            working_dir="/tmp/projeto",
        )
        with patch("src.adapters.claude_agent_sdk.ClaudeAgentOptions") as mock_opts:
            adapter._build_options()
            mock_opts.assert_called_once()
            kwargs = mock_opts.call_args[1]
            assert kwargs["model"] == "claude-sonnet-4-20250514"
            assert "cwd" in kwargs

    def test_build_options_sem_model(self):
        """Verifica que opções omitem model quando não configurado."""
        adapter = ClaudeAgentSDKAdapter()
        with patch("src.adapters.claude_agent_sdk.ClaudeAgentOptions") as mock_opts:
            adapter._build_options()
            mock_opts.assert_called_once()
            kwargs = mock_opts.call_args[1]
            assert "model" not in kwargs
            assert "cwd" not in kwargs
