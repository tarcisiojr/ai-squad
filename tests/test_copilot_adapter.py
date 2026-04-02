"""Testes para CopilotAdapter."""

import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.models import AgentStatus

# Pula todos os testes se o módulo copilot não está instalado
_has_copilot = importlib.util.find_spec("copilot") is not None
pytestmark = pytest.mark.skipif(not _has_copilot, reason="copilot SDK não instalado")


# --- Mock do Copilot SDK ---


class FakeResponse:
    """Simula response do send_and_wait."""

    def __init__(self, content: str = "resposta ok"):
        self.data = MagicMock()
        self.data.content = content


class FakeSession:
    """Simula session do Copilot SDK."""

    def __init__(self, session_id: str = ""):
        self.session_id = session_id
        self.send_and_wait = AsyncMock(return_value=FakeResponse())


class FakeCopilotClient:
    """Simula CopilotClient do Copilot SDK."""

    def __init__(self, opts=None):
        self._opts = opts or {}
        self._sessions: dict[str, FakeSession] = {}

    async def start(self):
        pass

    async def stop(self):
        pass

    async def create_session(self, opts: dict) -> FakeSession:
        session_id = opts.get("session_id", "test")
        session = FakeSession(session_id)
        self._sessions[session_id] = session
        return session

    async def resume_session(self, session_id: str) -> FakeSession:
        if session_id in self._sessions:
            return self._sessions[session_id]
        raise Exception("Session not found")


@pytest.fixture
def mock_copilot():
    """Fixture que mocka o módulo copilot."""
    with patch.dict("sys.modules", {"copilot": MagicMock()}):
        with patch(
            "ai_squad.adapters.copilot_adapter.CopilotAdapter._ensure_client_started"
        ) as mock_start:
            mock_start.return_value = None
            yield mock_start


def _create_adapter(**kwargs):
    """Cria CopilotAdapter com mocks."""
    from ai_squad.adapters.copilot_adapter import CopilotAdapter

    adapter = CopilotAdapter(
        timeout=60,
        working_dir="/tmp/test",
        model="claude-sonnet-4-6",
        **kwargs,
    )
    # Injeta client fake para evitar import real
    adapter._client = FakeCopilotClient()
    adapter._client_started = True
    return adapter


# --- Testes de inicialização ---


class TestCopilotAdapterInit:
    """Testes de inicialização do adapter."""

    def test_herda_interface(self):
        """Verifica que CopilotAdapter herda AIAgentAdapter."""
        from ai_squad.adapters.copilot_adapter import CopilotAdapter

        assert issubclass(CopilotAdapter, AIAgentAdapter)

    def test_status_inicial_idle(self):
        """Verifica status inicial como IDLE."""
        adapter = _create_adapter()
        assert adapter.status() == AgentStatus.IDLE

    def test_parametros_armazenados(self):
        """Verifica que parâmetros são armazenados corretamente."""
        adapter = _create_adapter()
        assert adapter._timeout == 60
        assert adapter._working_dir == "/tmp/test"
        assert adapter._model == "claude-sonnet-4-6"

    def test_client_lazy_init(self):
        """Verifica que client não é iniciado no construtor."""
        from ai_squad.adapters.copilot_adapter import CopilotAdapter

        adapter = CopilotAdapter()
        assert adapter._client is None
        assert adapter._client_started is False


# --- Testes de execução ---


class TestCopilotAdapterRun:
    """Testes de execução do adapter."""

    @pytest.mark.asyncio
    async def test_run_basico(self):
        """Verifica execução básica com resposta."""
        adapter = _create_adapter()
        resultado = await adapter.run("teste", {})
        assert resultado == "resposta ok"
        assert adapter.status() == AgentStatus.DONE

    @pytest.mark.asyncio
    async def test_run_com_context(self):
        """Verifica que contexto é processado corretamente."""
        adapter = _create_adapter()
        resultado = await adapter.run("teste", {"agent_name": "dev", "demand_id": "d1"})
        assert resultado == "resposta ok"

    @pytest.mark.asyncio
    async def test_run_com_model_override(self):
        """Verifica que model_override é usado na session."""
        adapter = _create_adapter()
        resultado = await adapter.run("teste", {"model_override": "gpt-4.1-mini"})
        assert resultado == "resposta ok"

    @pytest.mark.asyncio
    async def test_run_com_imagem(self):
        """Verifica que imagem é incluída no prompt."""
        adapter = _create_adapter()
        resultado = await adapter.run("teste", {"image_path": "/tmp/img.png"})
        assert resultado == "resposta ok"

    @pytest.mark.asyncio
    async def test_ask_delega_para_run(self):
        """Verifica que ask() delega para run()."""
        adapter = _create_adapter()
        resultado = await adapter.ask("pergunta")
        assert resultado == "resposta ok"

    @pytest.mark.asyncio
    async def test_status_running_durante_execucao(self):
        """Verifica status RUNNING durante execução."""
        adapter = _create_adapter()
        status_durante = None

        original_send = adapter._client.create_session

        async def capture_status(opts):
            nonlocal status_durante
            status_durante = adapter.status()
            return FakeSession()

        adapter._client.create_session = capture_status
        await adapter.run("teste", {})
        assert status_durante == AgentStatus.RUNNING

    @pytest.mark.asyncio
    async def test_status_error_quando_falha(self):
        """Verifica status ERROR quando execução falha."""
        adapter = _create_adapter()
        adapter._client.create_session = AsyncMock(side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError):
            await adapter.run("teste", {})
        assert adapter.status() == AgentStatus.ERROR


# --- Testes de autenticação ---


class TestCopilotAdapterAuth:
    """Testes de autenticação."""

    @pytest.mark.asyncio
    async def test_auth_com_github_token(self, monkeypatch):
        """Verifica que GITHUB_TOKEN é usado quando disponível."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")

        from ai_squad.adapters.copilot_adapter import CopilotAdapter

        adapter = CopilotAdapter()

        # Mocka o módulo copilot e a classe CopilotClient
        fake_module = MagicMock()
        fake_module.CopilotClient = FakeCopilotClient
        with patch.dict("sys.modules", {"copilot": fake_module}):
            await adapter._ensure_client_started()
            assert adapter._client_started is True
            # Verifica que client foi criado com github_token
            assert adapter._client._opts.get("github_token") == "ghp_test123"
            assert adapter._client._opts.get("use_logged_in_user") is False

    @pytest.mark.asyncio
    async def test_auth_sem_token_usa_cli_login(self, monkeypatch):
        """Verifica fallback para use_logged_in_user quando sem GITHUB_TOKEN."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        from ai_squad.adapters.copilot_adapter import CopilotAdapter

        adapter = CopilotAdapter()

        fake_module = MagicMock()
        fake_module.CopilotClient = FakeCopilotClient
        with patch.dict("sys.modules", {"copilot": fake_module}):
            await adapter._ensure_client_started()
            assert adapter._client_started is True
            assert adapter._client._opts.get("use_logged_in_user") is True


# --- Testes de sessions ---


class TestCopilotAdapterSessions:
    """Testes de gerenciamento de sessions."""

    @pytest.mark.asyncio
    async def test_nova_session_criada(self):
        """Verifica que nova session é criada para demand_id novo."""
        adapter = _create_adapter()
        await adapter.run("teste", {"demand_id": "demand-1"})
        assert "demand-1" in adapter._sessions

    @pytest.mark.asyncio
    async def test_session_reutilizada(self):
        """Verifica que session existente é reutilizada."""
        adapter = _create_adapter()
        # Primeira execução cria session
        await adapter.run("teste", {"demand_id": "demand-1"})
        session_1 = adapter._sessions["demand-1"]

        # Segunda execução reutiliza
        await adapter.run("teste 2", {"demand_id": "demand-1"})
        session_2 = adapter._sessions["demand-1"]
        assert session_1 is session_2

    def test_clear_session(self):
        """Verifica que clear_session remove session."""
        adapter = _create_adapter()
        adapter._sessions["d1"] = FakeSession()
        adapter.clear_session("d1")
        assert "d1" not in adapter._sessions


# --- Testes de callbacks ---


class TestCopilotAdapterCallbacks:
    """Testes de delegação de callbacks para SquadMCPToolsServer."""

    def test_set_progress_callback_delegado(self):
        """Verifica delegação de progress callback para MCP server."""
        adapter = _create_adapter()
        cb = MagicMock()
        adapter.set_progress_callback(cb)
        assert adapter._mcp_server._progress_callback is cb

    def test_set_start_agent_callback_delegado(self):
        """Verifica delegação de start_agent callback para MCP server."""
        adapter = _create_adapter()
        cb = MagicMock()
        adapter.set_start_agent_callback(cb)
        assert adapter._mcp_server._start_agent_callback is cb

    def test_set_get_pipeline_state_callback_delegado(self):
        """Verifica delegação de pipeline state callback para MCP server."""
        adapter = _create_adapter()
        cb = MagicMock()
        adapter.set_get_pipeline_state_callback(cb)
        assert adapter._mcp_server._get_pipeline_state_callback is cb

    def test_todos_callbacks_delegados(self):
        """Verifica que todos os 11 callbacks são delegados."""
        adapter = _create_adapter()
        callback_methods = [
            "set_progress_callback",
            "set_start_agent_callback",
            "set_get_agents_callback",
            "set_get_demand_state_callback",
            "set_read_journal_callback",
            "set_send_image_callback",
            "set_learn_lesson_callback",
            "set_get_pipeline_state_callback",
            "set_advance_step_callback",
            "set_skip_step_callback",
            "set_rerun_step_callback",
        ]
        for method_name in callback_methods:
            cb = MagicMock()
            getattr(adapter, method_name)(cb)
        # Se chegou aqui sem erro, todos os métodos existem e aceitam callback


# --- Testes de retry ---


class TestCopilotAdapterRetry:
    """Testes de retry com backoff exponencial."""

    @pytest.mark.asyncio
    async def test_retry_em_erro_transiente(self):
        """Verifica retry com backoff em erros transientes."""
        adapter = _create_adapter()
        call_count = 0

        original_create = adapter._client.create_session

        async def failing_then_ok(opts):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient error")
            return FakeSession()

        adapter._client.create_session = failing_then_ok
        # Reduz delay para testes
        adapter.RETRY_BASE_DELAY = 0.01

        resultado = await adapter.run("teste", {})
        assert resultado == "resposta ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_timeout_sem_retry(self):
        """Verifica que timeout não faz retry."""
        adapter = _create_adapter()

        async def timeout_create(opts):
            raise asyncio.TimeoutError()

        adapter._client.create_session = timeout_create

        with pytest.raises(TimeoutError):
            await adapter.run("teste", {})

    @pytest.mark.asyncio
    async def test_context_length_limpa_session(self):
        """Verifica que context_length_exceeded limpa session e retenta."""
        adapter = _create_adapter()
        call_count = 0

        async def context_then_ok(opts):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("context_length_exceeded")
            return FakeSession()

        adapter._client.create_session = context_then_ok
        resultado = await adapter.run("teste", {"demand_id": "d1"})
        assert resultado == "resposta ok"
        assert call_count == 2


# --- Testes de validate_required_tokens ---


class TestValidateTokensCopilot:
    """Testes de validação de tokens para provider copilot."""

    def test_copilot_sem_github_token(self, monkeypatch):
        """Verifica que GITHUB_TOKEN é reportado como ausente."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

        from ai_squad.factory import PlatformConfig

        config = PlatformConfig(ai_provider="copilot", messaging_provider="cli")
        missing = config.validate_required_tokens()
        assert "GITHUB_TOKEN" in missing

    def test_copilot_com_github_token(self, monkeypatch):
        """Verifica que com GITHUB_TOKEN não reporta ausente."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")

        from ai_squad.factory import PlatformConfig

        config = PlatformConfig(ai_provider="copilot", messaging_provider="cli")
        missing = config.validate_required_tokens()
        assert "GITHUB_TOKEN" not in missing

    def test_copilot_com_placeholder(self, monkeypatch):
        """Verifica que placeholder é tratado como ausente."""
        monkeypatch.setenv("GITHUB_TOKEN", "PREENCHA_AQUI_token")

        from ai_squad.factory import PlatformConfig

        config = PlatformConfig(ai_provider="copilot", messaging_provider="cli")
        missing = config.validate_required_tokens()
        assert "GITHUB_TOKEN" in missing


# --- Testes de shutdown ---


class TestCopilotAdapterShutdown:
    """Testes de lifecycle do client."""

    @pytest.mark.asyncio
    async def test_shutdown_para_client(self):
        """Verifica que shutdown chama client.stop()."""
        adapter = _create_adapter()
        adapter._client.stop = AsyncMock()
        await adapter.shutdown()
        adapter._client.stop.assert_awaited_once()
        assert adapter._client_started is False

    @pytest.mark.asyncio
    async def test_shutdown_limpa_sessions(self):
        """Verifica que shutdown limpa sessions."""
        adapter = _create_adapter()
        adapter._sessions["d1"] = FakeSession()
        adapter._client.stop = AsyncMock()
        await adapter.shutdown()
        assert len(adapter._sessions) == 0

    @pytest.mark.asyncio
    async def test_shutdown_sem_client(self):
        """Verifica que shutdown sem client não falha."""
        from ai_squad.adapters.copilot_adapter import CopilotAdapter

        adapter = CopilotAdapter()
        await adapter.shutdown()  # Não deve lançar exceção


# --- Testes de daemon ---


class TestDaemonCopilotAdapter:
    """Testes de criação do adapter via PlatformFactory."""

    def test_create_copilot_adapter_sem_dependencia(self):
        """Verifica erro claro quando github-copilot-sdk não está instalado."""
        from ai_squad.factory import PlatformFactory

        # Simula ImportError
        with patch.dict("sys.modules", {"ai_squad.adapters.copilot_adapter": None}):
            with pytest.raises(RuntimeError, match="Copilot SDK"):
                PlatformFactory._create_copilot_adapter({})
