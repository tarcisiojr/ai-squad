"""Testes para implementações do barramento de mensageria."""

import pytest

from src.messaging.cli import CLIMessageBus
from src.messaging.interface import MessageBus


class TestCLIMessageBus:
    """Testes para CLIMessageBus."""

    @pytest.fixture
    def bus(self):
        """Cria instância de CLIMessageBus."""
        return CLIMessageBus()

    def test_herda_message_bus(self, bus):
        """Verifica que CLIMessageBus implementa MessageBus."""
        assert isinstance(bus, MessageBus)

    @pytest.mark.asyncio
    async def test_send_message(self, bus, capsys):
        """Verifica que send_message exibe no stdout."""
        await bus.send_message("user1", "Olá mundo")
        captured = capsys.readouterr()
        assert "[user1] Olá mundo" in captured.out

    @pytest.mark.asyncio
    async def test_notify(self, bus, capsys):
        """Verifica que notify exibe notificação no stdout."""
        await bus.notify("user1", "Tarefa concluída")
        captured = capsys.readouterr()
        assert "[NOTIFICAÇÃO - user1]" in captured.out
        assert "Tarefa concluída" in captured.out

    @pytest.mark.asyncio
    async def test_receive_message_registra_callback(self, bus):
        """Verifica que receive_message registra o callback."""
        mensagens = []

        async def callback(texto):
            mensagens.append(texto)

        await bus.receive_message(callback)
        assert bus._message_callback is not None

    @pytest.mark.asyncio
    async def test_process_input_chama_callback(self, bus):
        """Verifica que process_input dispara o callback registrado."""
        mensagens = []

        async def callback(texto):
            mensagens.append(texto)

        await bus.receive_message(callback)
        await bus.process_input("teste de mensagem")
        assert "teste de mensagem" in mensagens

    @pytest.mark.asyncio
    async def test_process_input_sem_callback(self, bus):
        """Verifica que process_input sem callback não falha."""
        await bus.process_input("teste sem callback")

    @pytest.mark.asyncio
    async def test_receive_voice_registra_callback(self, bus):
        """Verifica que receive_voice registra o callback."""

        async def callback(audio):
            pass

        await bus.receive_voice(callback)
        assert bus._voice_callback is not None

    @pytest.mark.asyncio
    async def test_send_approval_request_exibe_opcoes(self, bus, capsys, monkeypatch):
        """Verifica que send_approval_request exibe as opções."""
        monkeypatch.setattr("builtins.input", lambda _: "1")
        resultado = await bus.send_approval_request("user1", "Aprovar plano?", ["Sim", "Não"])
        assert resultado == "Sim"
        captured = capsys.readouterr()
        assert "Aprovar plano?" in captured.out
        assert "1. Sim" in captured.out
        assert "2. Não" in captured.out
