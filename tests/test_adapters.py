"""Testes para implementações de AIAgentAdapter."""

import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.claude_code import ClaudeCodeAdapter, ClaudeCodeCLIAdapter
from src.adapters.interface import AIAgentAdapter
from src.models import AgentStatus


class TestClaudeCodeAdapter:
    """Testes para ClaudeCodeCLIAdapter (e alias ClaudeCodeAdapter)."""

    @pytest.fixture
    def adapter(self):
        """Cria instância de ClaudeCodeCLIAdapter."""
        return ClaudeCodeCLIAdapter(timeout=30)

    def test_alias_retrocompatibilidade(self):
        """Verifica que ClaudeCodeAdapter é alias para ClaudeCodeCLIAdapter."""
        assert ClaudeCodeAdapter is ClaudeCodeCLIAdapter

    def test_herda_ai_agent_adapter(self, adapter):
        """Verifica que ClaudeCodeAdapter implementa AIAgentAdapter."""
        assert isinstance(adapter, AIAgentAdapter)

    def test_status_inicial_idle(self, adapter):
        """Verifica que status inicial é IDLE."""
        assert adapter.status() == AgentStatus.IDLE

    @pytest.mark.asyncio
    async def test_run_sucesso(self, adapter):
        """Verifica execução com sucesso via subprocess mock."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Resultado do Claude"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            resultado = await adapter.run("Crie um hello world", {"lang": "python"})

        assert resultado == "Resultado do Claude"
        assert adapter.status() == AgentStatus.DONE

    @pytest.mark.asyncio
    async def test_run_timeout(self, adapter):
        """Verifica tratamento de timeout."""
        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 30)
        ):
            with pytest.raises(TimeoutError, match="excedeu timeout"):
                await adapter.run("prompt longo", {})

        assert adapter.status() == AgentStatus.ERROR

    @pytest.mark.asyncio
    async def test_run_erro_subprocess(self, adapter):
        """Verifica tratamento de erro do subprocess."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "claude", stderr="erro"),
        ):
            with pytest.raises(RuntimeError, match="retornou erro"):
                await adapter.run("prompt", {})

        assert adapter.status() == AgentStatus.ERROR

    @pytest.mark.asyncio
    async def test_run_cli_nao_encontrado(self, adapter):
        """Verifica tratamento quando CLI não está instalado."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(RuntimeError, match="não encontrado"):
                await adapter.run("prompt", {})

        assert adapter.status() == AgentStatus.ERROR

    @pytest.mark.asyncio
    async def test_ask_delega_para_run(self, adapter):
        """Verifica que ask delega para run com contexto vazio."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Resposta"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
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
        adapter = ClaudeCodeAdapter(timeout=600)
        assert adapter._timeout == 600

    def test_working_dir_configuravel(self):
        """Verifica que working_dir é configurável."""
        adapter = ClaudeCodeAdapter(working_dir="/tmp/projeto")
        assert adapter._working_dir == "/tmp/projeto"
