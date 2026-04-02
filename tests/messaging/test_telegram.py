"""Testes para TelegramMessageBus com mocks de API."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_squad.messaging.interface import MessageBus
from ai_squad.messaging.telegram import TelegramMessageBus


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
    async def test_send_message_com_thread_id(self, bus):
        """Verifica que send_message propaga message_thread_id."""
        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus.send_message("12345", "Msg no tópico", thread_id="999")

        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["message_thread_id"] == 999

    @pytest.mark.asyncio
    async def test_send_message_sem_thread_id(self, bus):
        """Verifica que send_message sem thread_id passa None."""
        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus.send_message("12345", "Msg geral")

        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["message_thread_id"] is None

    @pytest.mark.asyncio
    async def test_create_thread(self, bus):
        """Verifica criação de Forum Topic."""
        mock_bot = AsyncMock()
        mock_result = MagicMock()
        mock_result.message_thread_id = 42
        mock_bot.create_forum_topic.return_value = mock_result
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        thread_id = await bus.create_thread("12345", "Login OAuth")

        assert thread_id == "42"
        mock_bot.create_forum_topic.assert_called_once_with(
            chat_id="12345",
            name="Login OAuth",
        )

    @pytest.mark.asyncio
    async def test_create_thread_falha_retorna_none(self, bus):
        """Verifica que falha ao criar tópico retorna None."""
        mock_bot = AsyncMock()
        mock_bot.create_forum_topic.side_effect = Exception("API error")
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        thread_id = await bus.create_thread("12345", "Login OAuth")

        assert thread_id is None

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


class TestTelegramAccessControl:
    """Testes de controle de acesso por chat_id."""

    def test_is_authorized_sem_restricao_rejeita(self):
        """Sem allowed_chat_id configurado, rejeita qualquer chat (fail-closed)."""
        bus = TelegramMessageBus(token="fake-token")
        assert bus._is_authorized("12345") is False
        assert bus._is_authorized("99999") is False

    def test_is_authorized_com_restricao(self):
        """Com allowed_chat_id, apenas o chat configurado é autorizado."""
        bus = TelegramMessageBus(token="fake-token", allowed_chat_id="12345")
        assert bus._is_authorized("12345") is True
        assert bus._is_authorized("99999") is False

    def test_allowed_chat_id_armazenado(self):
        """Verifica que allowed_chat_id é armazenado corretamente."""
        bus = TelegramMessageBus(token="fake-token", allowed_chat_id="12345")
        assert bus._allowed_chat_id == "12345"

    @pytest.mark.asyncio
    async def test_handle_text_ignora_chat_nao_autorizado(self):
        """Mensagem de texto de chat não autorizado é ignorada silenciosamente."""
        bus = TelegramMessageBus(token="fake-token", allowed_chat_id="12345")
        callback = AsyncMock()
        await bus.receive_message(callback)

        # Mocka ApplicationBuilder para capturar handlers sem criar app real
        mock_app = MagicMock()
        mock_app.bot = AsyncMock()
        with patch("telegram.ext.ApplicationBuilder") as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            await bus._ensure_app()

        # Captura o handler de texto (primeiro registrado)
        text_handler_obj = mock_app.add_handler.call_args_list[0][0][0]

        update = MagicMock()
        update.message.chat_id = 99999
        update.message.from_user.id = 99999
        update.message.message_thread_id = None
        update.message.text = "mensagem invasora"

        await text_handler_obj.callback(update, MagicMock())

        # Callback NÃO deve ser chamado
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_text_aceita_chat_autorizado(self):
        """Mensagem de texto de chat autorizado é processada normalmente."""
        bus = TelegramMessageBus(token="fake-token", allowed_chat_id="12345")
        callback = AsyncMock()
        await bus.receive_message(callback)

        mock_app = MagicMock()
        mock_app.bot = AsyncMock()
        with patch("telegram.ext.ApplicationBuilder") as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            await bus._ensure_app()

        text_handler_obj = mock_app.add_handler.call_args_list[0][0][0]

        update = MagicMock()
        update.message.chat_id = 12345
        update.message.from_user.id = 67890
        update.message.message_thread_id = None
        update.message.text = "mensagem autorizada"

        await text_handler_obj.callback(update, MagicMock())

        callback.assert_called_once_with(
            "mensagem autorizada",
            thread_id=None,
            user_id="67890",
        )

    @pytest.mark.asyncio
    async def test_handle_text_propaga_thread_id(self):
        """Mensagem em Forum Topic propaga thread_id e user_id no callback."""
        bus = TelegramMessageBus(token="fake-token", allowed_chat_id="12345")
        callback = AsyncMock()
        await bus.receive_message(callback)

        mock_app = MagicMock()
        mock_app.bot = AsyncMock()
        with patch("telegram.ext.ApplicationBuilder") as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            await bus._ensure_app()

        text_handler_obj = mock_app.add_handler.call_args_list[0][0][0]

        update = MagicMock()
        update.message.chat_id = 12345
        update.message.from_user.id = 67890
        update.message.message_thread_id = 999
        update.message.text = "mensagem no tópico"

        await text_handler_obj.callback(update, MagicMock())

        callback.assert_called_once_with(
            "mensagem no tópico",
            thread_id="999",
            user_id="67890",
        )
