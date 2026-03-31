"""Testes para TUIMessageBus."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.messaging.interface import MessageBus
from src.messaging.tui import LOCAL_USER, TerminalGuard, TUIMessageBus


def _run(coro):
    """Helper para rodar coroutine em testes síncronos."""
    return asyncio.run(coro)


@pytest.fixture
def bus():
    """Cria instância de TUIMessageBus."""
    return TUIMessageBus(persona_name="Squad Test", persona_avatar="🤖")


class TestTUIMessageBus:
    """Testes básicos para TUIMessageBus."""

    def test_herda_message_bus(self, bus):
        """Verifica que TUIMessageBus implementa MessageBus."""
        assert isinstance(bus, MessageBus)

    def test_required_env_vars_vazio(self):
        """TUI não precisa de variáveis de ambiente."""
        assert TUIMessageBus.required_env_vars() == []

    def test_env_template_vazio(self):
        """TUI não precisa de template de .env."""
        assert TUIMessageBus.env_template() == ""

    def test_default_chat_id(self, bus):
        """Verifica que default_chat_id retorna LOCAL_USER."""
        assert bus.default_chat_id == LOCAL_USER

    def test_persona_configurada(self, bus):
        """Verifica configuração de persona."""
        assert bus._persona_name == "Squad Test"
        assert bus._persona_avatar == "🤖"


class TestTUISendMessage:
    """Testes para envio de mensagens."""

    def test_send_message_com_app(self, bus):
        """Verifica que send_message chama append_chat no app."""
        mock_app = MagicMock()
        bus._app = mock_app

        _run(bus.send_message("local", "Olá!"))

        mock_app.append_chat.assert_called_once()
        call_args = mock_app.append_chat.call_args
        assert "Olá!" in call_args[0][1]
        assert "Squad Test" in call_args[0][0]

    def test_send_message_com_sender_override(self, bus):
        """Verifica que sender via kwargs tem prioridade."""
        mock_app = MagicMock()
        bus._app = mock_app

        _run(bus.send_message("local", "Texto", sender="👨‍💼 Squad Lead"))

        call_args = mock_app.append_chat.call_args
        assert call_args[0][0] == "👨‍💼 Squad Lead"

    def test_send_message_sem_app(self, bus):
        """Verifica que send_message não falha sem app."""
        _run(bus.send_message("local", "Sem app"))

    def test_notify(self, bus):
        """Verifica que notify exibe com label de notificação."""
        mock_app = MagicMock()
        bus._app = mock_app

        _run(bus.notify("local", "Tarefa concluída"))

        call_args = mock_app.append_chat.call_args
        assert "🔔" in call_args[0][0]
        assert "Tarefa concluída" in call_args[0][1]


class TestTUICallbacks:
    """Testes para callbacks."""

    def test_receive_message_registra_callback(self, bus):
        """Verifica que receive_message armazena callback."""
        callback = AsyncMock()
        _run(bus.receive_message(callback))
        assert bus._message_callback is callback

    def test_receive_voice_registra_callback(self, bus):
        """Verifica que receive_voice armazena callback."""
        callback = AsyncMock()
        _run(bus.receive_voice(callback))
        assert bus._voice_callback is callback


class TestTUIUserInput:
    """Testes para input do usuário."""

    def test_on_user_input_resolve_pending_reply(self, bus):
        """Verifica que input resolve Future pendente."""
        mock_app = MagicMock()
        bus._app = mock_app

        async def _test():
            loop = asyncio.get_running_loop()
            bus._pending_reply = loop.create_future()
            await bus._on_user_input("42")
            return bus._pending_reply.result()

        result = _run(_test())
        assert result == "42"

    def test_on_user_input_exibe_no_chat(self, bus):
        """Verifica que input do usuário aparece no chat."""
        mock_app = MagicMock()
        bus._app = mock_app
        bus._message_callback = AsyncMock()

        _run(bus._on_user_input("Minha mensagem"))

        mock_app.append_chat.assert_called_once_with("👤 Você", "Minha mensagem")


class TestTUIRegistry:
    """Testes para registro no registry."""

    def test_tui_registrado(self):
        """Verifica que tui está registrado no registry."""
        from src.messaging.registry import get, load_builtin_providers

        load_builtin_providers()
        cls = get("tui")
        assert cls is TUIMessageBus


class TestTerminalGuard:
    """Testes para TerminalGuard — restauração de terminal."""

    def test_exit_restaura_fds_apos_excecao(self):
        """Verifica que __exit__ restaura fds mesmo após exceção."""
        try:
            with TerminalGuard():
                raise RuntimeError("erro simulado")
        except RuntimeError:
            pass

        # stdout e stderr devem estar restaurados (não None)
        assert sys.stdout is not None
        assert sys.stderr is not None

    def test_exit_restaura_termios_apos_excecao(self):
        """Verifica que __exit__ restaura termios quando disponível."""
        try:
            import termios  # noqa: F401
        except ImportError:
            pytest.skip("termios não disponível nesta plataforma")

        if not sys.stdin.isatty():
            pytest.skip("stdin não é TTY")

        import termios

        termios_antes = termios.tcgetattr(sys.stdin.fileno())

        try:
            with TerminalGuard():
                raise RuntimeError("erro simulado")
        except RuntimeError:
            pass

        termios_depois = termios.tcgetattr(sys.stdin.fileno())
        assert termios_antes == termios_depois

    def test_context_manager_sem_excecao(self):
        """Verifica que TerminalGuard funciona sem exceção."""
        stdout_antes = sys.stdout

        with TerminalGuard():
            pass

        # stdout deve estar preservado
        assert sys.stdout is stdout_antes

    def test_redirect_fds_com_log_path(self, tmp_path):
        """Verifica que redirect_fds redireciona para arquivo de log."""
        log_file = tmp_path / "test.log"
        log_file.touch()

        with TerminalGuard() as guard:
            guard.redirect_fds(str(log_file))
            # Após redirect, sys.stdout deve apontar para devnull
            assert sys.stdout is not None

        # Após sair do guard, stdout deve estar restaurado

    def test_redirect_fds_sem_log_path(self):
        """Verifica que redirect_fds funciona com log_path=None."""
        with TerminalGuard() as guard:
            guard.redirect_fds(None)

        # Não deve lançar exceção


class TestWaitForReplyTimeout:
    """Testes para timeout em _wait_for_reply."""

    def test_timeout_levanta_timeout_error(self, bus):
        """Verifica que _wait_for_reply levanta TimeoutError após timeout."""
        mock_app = MagicMock()
        bus._app = mock_app

        with pytest.raises(asyncio.TimeoutError):
            _run(bus._wait_for_reply(timeout=0.01))

        # Typing indicator deve ter sido limpo
        mock_app.set_typing.assert_called_with(None)
        # Mensagem de timeout deve ter sido exibida
        mock_app.append_chat.assert_called_once()
        call_args = mock_app.append_chat.call_args
        assert "Timeout" in call_args[0][0]

    def test_timeout_limpa_pending_reply(self, bus):
        """Verifica que pending_reply é None após timeout."""
        mock_app = MagicMock()
        bus._app = mock_app

        with pytest.raises(asyncio.TimeoutError):
            _run(bus._wait_for_reply(timeout=0.01))

        assert bus._pending_reply is None

    def test_reply_antes_do_timeout(self, bus):
        """Verifica que resposta antes do timeout funciona."""
        mock_app = MagicMock()
        bus._app = mock_app

        async def _test():
            # Agenda resposta em 10ms
            async def _respond():
                await asyncio.sleep(0.01)
                if bus._pending_reply and not bus._pending_reply.done():
                    bus._pending_reply.set_result("resposta")

            asyncio.create_task(_respond())
            return await bus._wait_for_reply(timeout=5.0)

        result = _run(_test())
        assert result == "resposta"


class TestTaskSupervision:
    """Testes para supervisão de tasks."""

    def test_on_task_done_exibe_erro_no_chat(self, bus):
        """Verifica que exceção em task é exibida no chat."""
        mock_app = MagicMock()
        bus._app = mock_app

        async def _failing_task():
            raise ValueError("algo deu errado")

        async def _test():
            task = bus._create_supervised_task(_failing_task())
            # Aguarda task completar
            try:
                await task
            except ValueError:
                pass
            # Aguarda callback ser processado
            await asyncio.sleep(0.01)

        _run(_test())

        # Typing deve ter sido limpo e erro exibido
        mock_app.set_typing.assert_called_with(None)
        mock_app.append_chat.assert_called()
        # Verifica que a mensagem de erro foi exibida
        call_args = mock_app.append_chat.call_args
        assert "Erro" in call_args[0][0]
        assert "algo deu errado" in call_args[0][1]

    def test_task_sucesso_remove_do_set(self, bus):
        """Verifica que task bem-sucedida é removida do set."""

        async def _ok_task():
            return "ok"

        async def _test():
            task = bus._create_supervised_task(_ok_task())
            await task
            await asyncio.sleep(0.01)

        _run(_test())

        assert len(bus._active_tasks) == 0

    def test_task_cancelada_nao_exibe_erro(self, bus):
        """Verifica que task cancelada não exibe erro no chat."""
        mock_app = MagicMock()
        bus._app = mock_app

        async def _slow_task():
            await asyncio.sleep(100)

        async def _test():
            task = bus._create_supervised_task(_slow_task())
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await asyncio.sleep(0.01)

        _run(_test())

        # Não deve ter chamado append_chat com erro
        mock_app.append_chat.assert_not_called()


class TestStopCancellation:
    """Testes para cancelamento no stop."""

    def test_stop_cancela_pending_reply(self, bus):
        """Verifica que stop cancela Future pendente."""

        async def _test():
            loop = asyncio.get_running_loop()
            bus._pending_reply = loop.create_future()
            await bus.stop()
            return bus._pending_reply.cancelled()

        assert _run(_test())

    def test_stop_cancela_tasks_ativas(self, bus):
        """Verifica que stop cancela todas as tasks ativas e limpa o set."""

        async def _slow_task():
            await asyncio.sleep(100)

        async def _test():
            task1 = bus._create_supervised_task(_slow_task())
            task2 = bus._create_supervised_task(_slow_task())
            assert len(bus._active_tasks) == 2

            await bus.stop()
            # Dá uma volta no event loop para processar cancelamentos
            await asyncio.sleep(0)

            assert task1.cancelled()
            assert task2.cancelled()
            assert len(bus._active_tasks) == 0

        _run(_test())

    def test_stop_sem_pendencias(self, bus):
        """Verifica que stop funciona sem nada pendente."""
        _run(bus.stop())
        # Não deve lançar exceção
