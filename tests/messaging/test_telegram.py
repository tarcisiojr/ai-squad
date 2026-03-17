"""Testes para TelegramMessageBus com mocks de API."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.messaging.telegram import TelegramMessageBus
from src.messaging.interface import MessageBus


class TestTelegramMessageBus:
    """Testes para TelegramMessageBus."""

    @pytest.fixture
    def bus(self):
        """Cria instância de TelegramMessageBus."""
        return TelegramMessageBus(
            token="fake-token",
            persona_name="PO Agent",
            persona_avatar="📋",
        )

    def test_herda_message_bus(self, bus):
        """Verifica que TelegramMessageBus implementa MessageBus."""
        assert isinstance(bus, MessageBus)

    def test_configuracao_persona(self, bus):
        """Verifica que a persona é configurada corretamente."""
        assert bus._persona_name == "PO Agent"
        assert bus._persona_avatar == "📋"
        assert bus._token == "fake-token"

    @pytest.mark.asyncio
    async def test_receive_message_registra_callback(self, bus):
        """Verifica que receive_message registra callback."""
        callback = AsyncMock()
        await bus.receive_message(callback)
        assert bus._message_callback is callback

    @pytest.mark.asyncio
    async def test_receive_voice_registra_callback(self, bus):
        """Verifica que receive_voice registra callback."""
        callback = AsyncMock()
        await bus.receive_voice(callback)
        assert bus._voice_callback is callback

    @pytest.mark.asyncio
    async def test_send_message_com_app_mock(self, bus):
        """Verifica envio de mensagem via bot do Telegram."""
        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus.send_message("12345", "Olá!")

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == "12345"
        assert "Olá!" in call_kwargs["text"]
        assert "PO Agent" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_notify_envia_com_prefixo(self, bus):
        """Verifica que notify envia com prefixo de notificação."""
        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus.notify("12345", "Tarefa concluída")

        mock_bot.send_message.assert_called_once()
        texto = mock_bot.send_message.call_args[1]["text"]
        assert "Tarefa concluída" in texto

    def test_persona_whisper_key(self):
        """Verifica configuração com chave Whisper."""
        bus = TelegramMessageBus(
            token="fake-token",
            whisper_api_key="sk-fake-whisper",
        )
        assert bus._whisper_api_key == "sk-fake-whisper"

    @pytest.mark.asyncio
    async def test_transcribe_voice_sem_api_key(self, bus):
        """Verifica que transcrição retorna None sem API key."""
        resultado = await bus._transcribe_voice(MagicMock(), MagicMock())
        assert resultado is None
