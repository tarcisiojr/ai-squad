"""Testes profundos para TUIMessageBus — cobertura de caminhos internos.

Nota: A renderizacao do terminal (SquadTUIApp._run com Textual) nao e testada
diretamente pois requer terminal real. Focamos em metodos helper e logica de dados.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_squad.messaging.tui import (
    LOCAL_USER,
    SquadTUIApp,
    TerminalGuard,
    TUIMessageBus,
)


def _run(coro):
    """Helper para rodar coroutine."""
    return asyncio.run(coro)


@pytest.fixture
def bus():
    """Cria instancia de TUIMessageBus."""
    return TUIMessageBus(persona_name="TestSquad", persona_avatar="🤖")


# --- _wait_for_reply ---


class TestWaitForReply:
    """Testes para _wait_for_reply com timeout e cancelamento."""

    def test_wait_for_reply_timeout(self, bus):
        """Verifica que timeout levanta TimeoutError."""
        mock_app = MagicMock()
        bus._app = mock_app

        with pytest.raises(asyncio.TimeoutError):
            _run(bus._wait_for_reply(timeout=0.01))

        # Deve ter mostrado mensagem de timeout no chat
        mock_app.append_chat.assert_called()
        call_text = mock_app.append_chat.call_args[0][1]
        assert "expirou" in call_text.lower() or "timeout" in call_text.lower()

    def test_wait_for_reply_timeout_sem_app(self, bus):
        """Timeout sem app nao falha."""
        bus._app = None

        with pytest.raises(asyncio.TimeoutError):
            _run(bus._wait_for_reply(timeout=0.01))

    def test_wait_for_reply_limpa_pending(self, bus):
        """Verifica que pending_reply e limpo apos timeout."""
        bus._app = MagicMock()

        with pytest.raises(asyncio.TimeoutError):
            _run(bus._wait_for_reply(timeout=0.01))

        assert bus._pending_reply is None


# --- _create_supervised_task ---


class TestSupervisedTask:
    """Testes para _create_supervised_task e _on_task_done."""

    def test_create_supervised_task_adiciona_ao_set(self, bus):
        """Verifica que task e adicionada ao set de tasks ativas."""

        async def _test():
            coro = asyncio.sleep(10)
            task = bus._create_supervised_task(coro)
            assert task in bus._active_tasks
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        _run(_test())

    def test_on_task_done_remove_do_set(self, bus):
        """Verifica que task concluida e removida do set."""

        async def _test():
            async def quick():
                return "done"

            task = bus._create_supervised_task(quick())
            await task
            # Callback deve ter removido do set
            await asyncio.sleep(0.01)
            assert task not in bus._active_tasks

        _run(_test())

    def test_on_task_done_cancelled(self, bus):
        """Verifica que task cancelada nao gera erro."""

        async def _test():
            task = bus._create_supervised_task(asyncio.sleep(100))
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await asyncio.sleep(0.01)
            assert task not in bus._active_tasks

        _run(_test())

    def test_on_task_done_com_excecao_mostra_erro(self, bus):
        """Verifica que task com excecao mostra erro no chat."""
        mock_app = MagicMock()
        bus._app = mock_app

        async def _test():
            async def failing():
                raise RuntimeError("task falhou")

            task = bus._create_supervised_task(failing())
            # Aguarda task terminar
            await asyncio.sleep(0.05)

        _run(_test())

        # Deve ter mostrado erro no chat
        mock_app.append_chat.assert_called()


# --- _on_user_input caminhos adicionais ---


class TestOnUserInputDeep:
    """Testes adicionais para _on_user_input."""

    def test_input_resolve_pending_reply(self, bus):
        """Input resolve pending_reply quando existe."""
        mock_app = MagicMock()
        bus._app = mock_app

        async def _test():
            bus._pending_reply = asyncio.get_event_loop().create_future()
            await bus._on_user_input("resposta")
            return bus._pending_reply.result()

        result = _run(_test())
        assert result == "resposta"

    def test_input_com_callback_erro_mostra_no_chat(self, bus):
        """Erro no callback mostra mensagem no chat."""
        mock_app = MagicMock()
        bus._app = mock_app

        # Callback que lanca excecao sincrona no create_task
        bus._message_callback = MagicMock(side_effect=Exception("callback error"))

        async def _test():
            await bus._on_user_input("texto com erro")

        _run(_test())

        # Deve ter mostrado erro no chat
        assert mock_app.append_chat.call_count >= 2  # "Voce" + erro

    def test_input_sem_app_nao_falha(self, bus):
        """Input sem app nao falha."""
        bus._app = None
        bus._message_callback = None

        _run(bus._on_user_input("texto"))


# --- stop com pending e tasks ---


class TestStopDeep:
    """Testes adicionais para stop."""

    def test_stop_cancela_pending_reply(self, bus):
        """Stop cancela future pendente."""

        async def _test():
            bus._pending_reply = asyncio.get_event_loop().create_future()
            await bus.stop()
            assert bus._pending_reply.cancelled()

        _run(_test())

    def test_stop_cancela_tasks_ativas(self, bus):
        """Stop cancela todas as tasks ativas."""

        async def _test():
            task1 = bus._create_supervised_task(asyncio.sleep(100))
            task2 = bus._create_supervised_task(asyncio.sleep(100))
            await bus.stop()
            # Aguarda tasks serem processadas pelo event loop
            await asyncio.sleep(0.01)
            # Apos stop, set e limpo
            assert len(bus._active_tasks) == 0
            # Tasks devem estar canceladas ou em estado de cancelamento
            assert task1.done()
            assert task2.done()

        _run(_test())

    def test_stop_sem_pending_sem_app(self, bus):
        """Stop sem pending nem app nao falha."""

        _run(bus.stop())


# --- send_message caminhos ---


class TestSendMessageDeep:
    """Testes para send_message — caminhos nao cobertos."""

    def test_send_message_sem_sender_usa_persona(self, bus):
        """Sem sender, usa persona do bus."""
        mock_app = MagicMock()
        bus._app = mock_app

        _run(bus.send_message("local", "texto"))

        call_args = mock_app.append_chat.call_args
        assert "TestSquad" in call_args[0][0]

    def test_send_message_com_sender_override(self, bus):
        """Sender override tem prioridade."""
        mock_app = MagicMock()
        bus._app = mock_app

        _run(bus.send_message("local", "texto", sender="📋 PO"))

        call_args = mock_app.append_chat.call_args
        assert call_args[0][0] == "📋 PO"

    def test_send_message_sem_app(self, bus):
        """send_message sem app nao falha."""
        bus._app = None
        _run(bus.send_message("local", "texto"))


# --- notify ---


class TestNotifyDeep:
    """Testes para notify."""

    def test_notify_com_app(self, bus):
        """Notify com app exibe mensagem."""
        mock_app = MagicMock()
        bus._app = mock_app

        _run(bus.notify("local", "Tarefa concluida"))

        mock_app.append_chat.assert_called_once()
        assert "Tarefa concluida" in mock_app.append_chat.call_args[0][1]

    def test_notify_sem_app(self, bus):
        """Notify sem app nao falha."""
        bus._app = None
        _run(bus.notify("local", "Tarefa"))


# --- receive_message / receive_voice ---


class TestReceiveCallbacks:
    """Testes para registro de callbacks."""

    def test_receive_message(self, bus):
        """Registra callback de mensagem."""
        cb = AsyncMock()
        _run(bus.receive_message(cb))
        assert bus._message_callback is cb

    def test_receive_voice(self, bus):
        """Registra callback de voz."""
        cb = AsyncMock()
        _run(bus.receive_voice(cb))
        assert bus._voice_callback is cb


# --- env_vars e propriedades ---


class TestPropriedades:
    """Testes para propriedades e classmethod."""

    def test_required_env_vars_vazio(self):
        """TUI nao precisa de env vars."""
        assert TUIMessageBus.required_env_vars() == []

    def test_env_template_vazio(self):
        """TUI nao precisa de template."""
        assert TUIMessageBus.env_template() == ""

    def test_default_chat_id(self, bus):
        """Retorna LOCAL_USER."""
        assert bus.default_chat_id == LOCAL_USER


# --- TerminalGuard context manager ---


class TestTerminalGuardContextManager:
    """Testes para TerminalGuard como context manager."""

    def test_enter_salva_estado(self):
        """Verifica que __enter__ salva stdout/stderr."""
        guard = TerminalGuard()
        result = guard.__enter__()
        assert result is guard
        assert guard._saved_stdout is not None
        assert guard._saved_stderr is not None
        guard.__exit__(None, None, None)

    def test_exit_restaura_estado(self):
        """Verifica que __exit__ restaura stdout/stderr."""
        import sys
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        guard = TerminalGuard()
        guard.__enter__()
        guard.__exit__(None, None, None)

        assert sys.stdout is original_stdout
        assert sys.stderr is original_stderr

    def test_redirect_fds_sem_tty(self):
        """Verifica redirect_fds sem tty disponivel."""
        guard = TerminalGuard()
        guard.__enter__()

        # Redireciona para devnull
        guard.redirect_fds(None)

        guard.__exit__(None, None, None)

    def test_redirect_fds_com_log_path(self, tmp_path):
        """Verifica redirect_fds com log file."""
        guard = TerminalGuard()
        guard.__enter__()

        log_file = tmp_path / "test.log"
        guard.redirect_fds(str(log_file))

        guard.__exit__(None, None, None)
