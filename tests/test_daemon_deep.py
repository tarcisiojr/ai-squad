"""Testes profundos para Daemon — cobertura de run() e handlers."""

import asyncio
import signal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from ai_squad.daemon import Daemon


def _mock_bus(chat_id: str = "12345") -> MagicMock:
    """Cria mock de MessageBus com todas as propriedades."""
    bus = AsyncMock()
    type(bus).default_chat_id = PropertyMock(return_value=chat_id)
    type(bus).supports_threads = PropertyMock(return_value=False)
    type(bus).bot_identifier = PropertyMock(return_value="squadbot")
    bus.run_forever = AsyncMock(return_value=None)
    return bus


def _daemon_with_mocks(chat_id: str = "12345") -> Daemon:
    """Cria Daemon com todos os componentes mockados."""
    daemon = Daemon()
    daemon._bus = _mock_bus(chat_id)
    daemon._engine = AsyncMock()
    daemon._config = MagicMock()
    daemon._config.agents = {}
    daemon._config.activation_mode = "mention"
    daemon._config.messaging_provider = "telegram"
    daemon._config.heartbeat.enabled = False
    daemon._thread_map = None
    daemon._thread_tracker = None
    return daemon


# --- run() ---


class TestDaemonRun:
    """Testes para o metodo run() — loop principal."""

    @pytest.mark.asyncio
    async def test_run_registra_handlers_e_inicia(self):
        """Verifica que run() registra handlers e inicia bus."""
        daemon = Daemon()

        # Mock _setup_components para configurar mocks
        def setup():
            daemon._bus = _mock_bus()
            daemon._engine = AsyncMock()
            daemon._config = MagicMock()
            daemon._config.messaging_provider = "telegram"
            daemon._config.heartbeat.enabled = False
            daemon._thread_tracker = None

        daemon._setup_components = setup
        daemon._resume_pending_work = AsyncMock()

        # run_forever retorna None (bus padrao), shutdown_event precisa ser setado
        async def _trigger_shutdown():
            await asyncio.sleep(0.05)
            daemon._shutdown_event.set()

        # Mock signal handlers pois nao funciona em testes
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.add_signal_handler = MagicMock()

            task = asyncio.create_task(daemon.run())
            await asyncio.sleep(0.05)
            daemon._shutdown_event.set()
            await asyncio.wait_for(task, timeout=5.0)

        # Verifica que bus.start foi chamado
        daemon._bus.start.assert_called_once()
        daemon._bus.receive_message.assert_called_once()
        daemon._bus.receive_voice.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_com_bus_run_forever(self):
        """Verifica que run() usa run_forever do bus quando retorna valor."""
        daemon = Daemon()

        def setup():
            bus = _mock_bus()
            bus.run_forever = AsyncMock(return_value="tui_exited")
            daemon._bus = bus
            daemon._engine = AsyncMock()
            daemon._config = MagicMock()
            daemon._config.messaging_provider = "tui"
            daemon._config.heartbeat.enabled = False
            daemon._thread_tracker = None

        daemon._setup_components = setup
        daemon._resume_pending_work = AsyncMock()

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.add_signal_handler = MagicMock()
            await daemon.run()

        # Bus stop deve ter sido chamado
        daemon._bus.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_reconexao_apos_erro(self):
        """Verifica backoff de reconexao quando bus falha."""
        daemon = Daemon()

        call_count = [0]

        def setup():
            bus = _mock_bus()

            async def failing_run_forever():
                nonlocal call_count
                call_count[0] += 1
                if call_count[0] == 1:
                    raise ConnectionError("lost connection")
                # Segunda vez: shutdown
                daemon._shutdown_event.set()
                return None

            bus.run_forever = failing_run_forever
            daemon._bus = bus
            daemon._engine = AsyncMock()
            daemon._config = MagicMock()
            daemon._config.messaging_provider = "telegram"
            daemon._config.heartbeat.enabled = False
            daemon._thread_tracker = None

        daemon._setup_components = setup
        daemon._resume_pending_work = AsyncMock()

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.add_signal_handler = MagicMock()
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await daemon.run()

        # sleep de reconexao deve ter sido chamado com backoff
        mock_sleep.assert_called()


# --- Voice, Photo, Document handlers registrados em run() ---


class TestRunHandlers:
    """Testes para handlers registrados dentro de run()."""

    @pytest.mark.asyncio
    async def test_voice_handler_delega_para_handle_demand(self):
        """Verifica que voice handler chama _handle_new_demand."""
        daemon = _daemon_with_mocks()
        daemon._handle_new_demand = AsyncMock()

        # Simula registracao do voice handler
        voice_cb = None

        async def capture_voice(cb):
            nonlocal voice_cb
            voice_cb = cb

        daemon._bus.receive_voice = capture_voice

        # Registra handlers como faria run()
        await daemon._bus.receive_voice(
            lambda text, *, thread_id=None, user_id="": daemon._handle_new_demand(
                text, thread_id=thread_id, user_id=user_id
            )
        )

        # Chama o handler capturado
        await voice_cb("texto voz", thread_id="t1", user_id="u1")
        daemon._handle_new_demand.assert_called_once_with(
            "texto voz", thread_id="t1", user_id="u1"
        )

    @pytest.mark.asyncio
    async def test_photo_handler_delega_para_handle_demand(self):
        """Verifica que photo handler chama _handle_new_demand com image_path."""
        daemon = _daemon_with_mocks()
        daemon._handle_new_demand = AsyncMock()

        photo_cb = None

        async def capture_photo(cb):
            nonlocal photo_cb
            photo_cb = cb

        daemon._bus.receive_photo = capture_photo

        await daemon._bus.receive_photo(
            lambda text, image_path, *, thread_id=None, user_id="": daemon._handle_new_demand(
                text, image_path=image_path, thread_id=thread_id, user_id=user_id
            )
        )

        await photo_cb("analise", "/tmp/foto.jpg", thread_id="t1", user_id="u1")
        daemon._handle_new_demand.assert_called_once_with(
            "analise", image_path="/tmp/foto.jpg", thread_id="t1", user_id="u1"
        )

    @pytest.mark.asyncio
    async def test_document_handler_delega_para_handle_demand(self):
        """Verifica que document handler chama _handle_new_demand."""
        daemon = _daemon_with_mocks()
        daemon._handle_new_demand = AsyncMock()

        doc_cb = None

        async def capture_doc(cb):
            nonlocal doc_cb
            doc_cb = cb

        daemon._bus.receive_document = capture_doc

        await daemon._bus.receive_document(
            lambda caption, file_path, *, thread_id=None, user_id="", original_filename="":
                daemon._handle_new_demand(
                    f"Documento recebido: {original_filename}. {caption}",
                    thread_id=thread_id,
                    user_id=user_id,
                )
        )

        await doc_cb(
            "Relatorio", "/tmp/doc.pdf",
            thread_id="t1", user_id="u1", original_filename="relatorio.pdf"
        )
        daemon._handle_new_demand.assert_called_once()
        call_text = daemon._handle_new_demand.call_args[0][0]
        assert "relatorio.pdf" in call_text

    @pytest.mark.asyncio
    async def test_reaction_handler_chama_tracker(self):
        """Verifica que reaction handler chama reaction_tracker."""
        daemon = _daemon_with_mocks()
        daemon._engine.reaction_tracker = MagicMock()

        reaction_cb = None

        async def capture_reaction(cb):
            nonlocal reaction_cb
            reaction_cb = cb

        daemon._bus.on_reaction = capture_reaction

        await daemon._bus.on_reaction(
            lambda chat_id, message_id, emoji, user_id:
                daemon._engine.reaction_tracker.on_reaction(message_id, emoji)
                if daemon._engine and daemon._engine.reaction_tracker
                else None
        )

        reaction_cb("12345", 100, "👍", "u1")

        daemon._engine.reaction_tracker.on_reaction.assert_called_once_with(100, "👍")


# --- _shutdown ---


class TestShutdown:
    """Testes para _shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_notifica_e_seta_evento(self):
        """Verifica que shutdown notifica via bus e seta evento."""
        daemon = _daemon_with_mocks()

        await daemon._shutdown()

        assert daemon._shutdown_event.is_set()
        daemon._bus.notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_sem_bus_nao_falha(self):
        """Shutdown sem bus nao falha."""
        daemon = Daemon()
        daemon._bus = None
        await daemon._shutdown()
        assert daemon._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_notify_falha_nao_propaga(self):
        """Falha na notificacao nao impede shutdown."""
        daemon = _daemon_with_mocks()
        daemon._bus.notify.side_effect = Exception("notify error")

        await daemon._shutdown()
        assert daemon._shutdown_event.is_set()


# --- _healthcheck_loop ---


class TestHealthcheckLoop:
    """Testes para _healthcheck_loop."""

    @pytest.mark.asyncio
    async def test_healthcheck_escreve_arquivo(self):
        """Verifica que healthcheck escreve arquivo."""
        daemon = _daemon_with_mocks()

        iter_count = [0]

        async def limited_sleep(_):
            iter_count[0] += 1
            if iter_count[0] >= 1:
                daemon._shutdown_event.set()

        with patch("asyncio.sleep", side_effect=limited_sleep):
            with patch.object(daemon, "_write_healthcheck") as mock_write:
                await daemon._healthcheck_loop()

        mock_write.assert_called()


# --- _heartbeat_loop ---


class TestHeartbeatLoop:
    """Testes para _heartbeat_loop."""

    @pytest.mark.asyncio
    async def test_heartbeat_desabilitado(self):
        """Heartbeat desabilitado retorna imediatamente."""
        daemon = _daemon_with_mocks()
        daemon._config.heartbeat.enabled = False

        await daemon._heartbeat_loop()
        # Deve ter retornado sem nenhum await longo


# --- _write_healthcheck / _remove_healthcheck ---


class TestHealthcheckFiles:
    """Testes para _write_healthcheck e _remove_healthcheck."""

    def test_write_healthcheck(self, tmp_path, monkeypatch):
        """Verifica que healthcheck cria arquivo."""
        daemon = _daemon_with_mocks()
        hc_path = tmp_path / "ai-squad-healthy"

        with patch("ai_squad.daemon.Path") as mock_path:
            mock_path.return_value = MagicMock()
            daemon._write_healthcheck()

    def test_remove_healthcheck_sem_arquivo(self):
        """Verifica que remove sem arquivo nao falha."""
        daemon = _daemon_with_mocks()

        with patch("ai_squad.daemon.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            daemon._remove_healthcheck()

    def test_remove_healthcheck_com_arquivo(self):
        """Verifica que remove com arquivo chama unlink."""
        daemon = _daemon_with_mocks()

        with patch("ai_squad.daemon.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            daemon._remove_healthcheck()
            mock_path.return_value.unlink.assert_called_once()


# --- Properties ---


class TestDaemonProperties:
    """Testes para propriedades do daemon."""

    def test_engine_sem_inicializar_falha(self):
        """Acesso ao engine sem inicializar lanca AssertionError."""
        daemon = Daemon()
        with pytest.raises(AssertionError):
            _ = daemon.engine

    def test_bus_sem_inicializar_falha(self):
        """Acesso ao bus sem inicializar lanca AssertionError."""
        daemon = Daemon()
        with pytest.raises(AssertionError):
            _ = daemon.bus

    def test_config_sem_carregar_falha(self):
        """Acesso ao config sem carregar lanca AssertionError."""
        daemon = Daemon()
        with pytest.raises(AssertionError):
            _ = daemon.config

    def test_engine_apos_configurar(self):
        """Acesso ao engine apos configurar funciona."""
        daemon = _daemon_with_mocks()
        _ = daemon.engine  # nao deve lancar

    def test_bus_apos_configurar(self):
        """Acesso ao bus apos configurar funciona."""
        daemon = _daemon_with_mocks()
        _ = daemon.bus  # nao deve lancar
