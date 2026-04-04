"""Testes adicionais para cobertura do daemon — run(), standby, healthcheck."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from ai_squad.daemon import Daemon


def _mock_bus(chat_id: str = "12345") -> MagicMock:
    """Cria mock de MessageBus com default_chat_id configurado."""
    bus = AsyncMock()
    type(bus).default_chat_id = PropertyMock(return_value=chat_id)
    type(bus).supports_threads = PropertyMock(return_value=False)
    type(bus).bot_identifier = PropertyMock(return_value="squadbot")
    return bus


def _daemon_with_mocks(chat_id: str = "12345") -> Daemon:
    """Cria Daemon com bus, engine e config mockados."""
    daemon = Daemon()
    daemon._bus = _mock_bus(chat_id)
    daemon._engine = AsyncMock()
    daemon._config = MagicMock()
    daemon._config.agents = {}
    daemon._config.activation_mode = "mention"
    daemon._thread_map = None
    daemon._thread_tracker = None
    return daemon


class TestStandbyTimeoutLoopWithStaleThreads:
    """Testes para _standby_timeout_loop com threads stale."""

    @pytest.mark.asyncio
    async def test_loop_envia_mensagem_para_threads_stale(self):
        """Loop detecta threads stale e envia mensagem."""
        daemon = _daemon_with_mocks()
        daemon._thread_tracker = MagicMock()
        daemon._thread_tracker.standby_timeout = 300
        daemon._thread_tracker.get_stale_standby_threads.return_value = [
            ("thread-1", {"user": "user1"}),
        ]

        # Faz o loop rodar uma iteração e parar
        call_count = [0]

        def is_set_once():
            call_count[0] += 1
            return call_count[0] > 1

        daemon._shutdown_event.is_set = is_set_once

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await daemon._standby_timeout_loop()

        daemon._bus.send_message.assert_called_once()
        daemon._thread_tracker.reactivate.assert_called_once_with("thread-1")

    @pytest.mark.asyncio
    async def test_loop_cancellado_para_limpo(self):
        """CancelledError para o loop sem propagação."""
        daemon = _daemon_with_mocks()
        daemon._thread_tracker = MagicMock()
        daemon._thread_tracker.standby_timeout = 300
        daemon._thread_tracker.get_stale_standby_threads.side_effect = asyncio.CancelledError()

        call_count = [0]

        def is_set_once():
            call_count[0] += 1
            return call_count[0] > 1

        daemon._shutdown_event.is_set = is_set_once

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await daemon._standby_timeout_loop()

    @pytest.mark.asyncio
    async def test_loop_erro_generico_continua(self):
        """Erro genérico no loop é capturado e continua."""
        daemon = _daemon_with_mocks()
        daemon._thread_tracker = MagicMock()
        daemon._thread_tracker.standby_timeout = 300

        call_count = [0]

        def side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Erro temporário")
            return []

        daemon._thread_tracker.get_stale_standby_threads.side_effect = side_effect

        iteration = [0]

        def is_set():
            iteration[0] += 1
            return iteration[0] > 2

        daemon._shutdown_event.is_set = is_set

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await daemon._standby_timeout_loop()


class TestHealthcheckLoop:
    """Testes adicionais para _healthcheck_loop."""

    @pytest.mark.asyncio
    async def test_healthcheck_escreve_arquivo(self):
        """Healthcheck escreve arquivo periodicamente."""
        daemon = Daemon()

        # Faz o loop rodar uma iteração e parar
        call_count = [0]

        def is_set_once():
            call_count[0] += 1
            return call_count[0] > 1

        daemon._shutdown_event.is_set = is_set_once

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch.object(daemon, "_write_healthcheck") as mock_write:
                await daemon._healthcheck_loop()
                mock_write.assert_called_once()


class TestSetupLogging:
    """Testes para _setup_logging."""

    def test_cria_diretorio_de_logs(self, tmp_path):
        """Cria diretório de logs e configura handler."""
        from ai_squad.path_resolver import PathResolver

        paths = PathResolver("local", tmp_path)
        (tmp_path / ".ai-squad").mkdir(exist_ok=True)

        daemon = Daemon(path_resolver=paths)
        daemon._setup_logging()

        logs_dir = paths.state_dir.parent / "logs"
        assert logs_dir.exists()


class TestRemoveHealthcheck:
    """Testes para _remove_healthcheck."""

    def test_remove_arquivo_existente(self):
        """Remove arquivo de healthcheck quando existe."""
        health = Path("/tmp/ai-squad-healthy")
        health.touch()
        assert health.exists()

        daemon = Daemon()
        daemon._remove_healthcheck()
        assert not health.exists()

    def test_remove_arquivo_inexistente(self):
        """Não falha ao remover arquivo inexistente."""
        health = Path("/tmp/ai-squad-healthy")
        if health.exists():
            health.unlink()

        daemon = Daemon()
        daemon._remove_healthcheck()  # Não deve lançar exceção


class TestLoadConfigEdgeCases:
    """Testes adicionais para _load_config."""

    def test_config_com_ai_model_env(self, monkeypatch, tmp_path):
        """AI_MODEL é sobrescrito por env var."""
        from ai_squad.path_resolver import PathResolver

        paths = PathResolver("local", tmp_path)
        (tmp_path / ".ai-squad").mkdir(exist_ok=True)

        monkeypatch.delenv("AI_PROVIDER", raising=False)
        monkeypatch.delenv("MESSAGING_PROVIDER", raising=False)
        monkeypatch.setenv("AI_MODEL", "claude-opus")

        daemon = Daemon(path_resolver=paths)
        config = daemon._load_config()
        assert config.ai_model == "claude-opus"

    def test_config_sem_env_sem_yaml(self, monkeypatch, tmp_path):
        """Config padrão quando não há env vars nem YAML."""
        from ai_squad.path_resolver import PathResolver

        paths = PathResolver("local", tmp_path)
        (tmp_path / ".ai-squad").mkdir(exist_ok=True)

        for var in [
            "AI_PROVIDER", "MESSAGING_PROVIDER", "AI_MODEL",
            "AGENT_TIMEOUT", "LIGHT_MODEL", "HEAVY_MODEL",
            "STATE_DIR", "REPO_PATH",
        ]:
            monkeypatch.delenv(var, raising=False)

        daemon = Daemon(path_resolver=paths)
        config = daemon._load_config()
        assert config.ai_provider == "claude-agent-sdk"
        assert config.messaging_provider == "telegram"


class TestDaemonProperties:
    """Testes para propriedades do Daemon."""

    def test_engine_property_falha_sem_init(self):
        """engine property falha se não inicializado."""
        daemon = Daemon()
        with pytest.raises(AssertionError, match="Engine"):
            _ = daemon.engine

    def test_bus_property_falha_sem_init(self):
        """bus property falha se não inicializado."""
        daemon = Daemon()
        with pytest.raises(AssertionError, match="MessageBus"):
            _ = daemon.bus

    def test_config_property_falha_sem_init(self):
        """config property falha se não carregada."""
        daemon = Daemon()
        daemon._config = None
        with pytest.raises(AssertionError, match="Config"):
            _ = daemon.config


class TestHandleNewDemandWithImage:
    """Testes para _handle_new_demand com imagem."""

    @pytest.mark.asyncio
    async def test_imagem_inexistente_nao_falha(self):
        """Imagem que não existe na limpeza não falha."""
        daemon = _daemon_with_mocks()
        await daemon._handle_new_demand("Texto", "/nao/existe/img.png")

    @pytest.mark.asyncio
    async def test_erro_notificar_falha_silencioso(self):
        """Erro ao notificar falha não propaga exceção."""
        daemon = _daemon_with_mocks()
        daemon._engine.run_squad_lead.side_effect = RuntimeError("Boom")
        daemon._bus.notify.side_effect = RuntimeError("Falha no notify")

        await daemon._handle_new_demand("Texto que falha")
        # Não deve lançar exceção


class TestHandleNewDemandAgentCommands:
    """Testes para roteamento de comandos de agente."""

    @pytest.mark.asyncio
    async def test_comando_agente_com_thread_routed(self):
        """Comando de agente em thread mapeada usa demand existente."""
        agent = MagicMock()
        agent.command = "/po"
        agent.name = "PO Agent"
        daemon = _daemon_with_mocks()
        daemon._config.agents = {"po": agent}
        daemon._thread_map = MagicMock()
        daemon._thread_map.get_demand.return_value = "demand-existente"

        await daemon._handle_new_demand("/po Analisar specs", thread_id="t1")

        # Deve ter criado task para conversa direta
        await asyncio.sleep(0.05)


class TestShutdownNotifica:
    """Testes adicionais para _shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_notifica_via_bus(self):
        """Shutdown envia notificação de encerramento."""
        daemon = Daemon()
        daemon._bus = _mock_bus("12345")

        await daemon._shutdown()

        daemon._bus.notify.assert_called_once()
        msg = daemon._bus.notify.call_args[0][1]
        assert "encerrando" in msg

    @pytest.mark.asyncio
    async def test_shutdown_erro_notify_silencioso(self):
        """Shutdown continua se notificação falha."""
        daemon = Daemon()
        daemon._bus = _mock_bus("12345")
        daemon._bus.notify.side_effect = RuntimeError("Erro")

        await daemon._shutdown()
        assert daemon._shutdown_event.is_set()
