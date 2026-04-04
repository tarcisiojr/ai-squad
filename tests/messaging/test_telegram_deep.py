"""Testes profundos para TelegramMessageBus — cobertura de handlers internos."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_squad.messaging.telegram import TelegramMessageBus


@pytest.fixture
def bus():
    """Cria instancia de TelegramMessageBus com allowed_chat_id."""
    return TelegramMessageBus(
        token="fake-token",
        persona_name="PO Agent",
        persona_avatar="📋",
        allowed_chat_id="12345",
        activation_mode="all",
    )


async def _setup_app(bus):
    """Inicializa app mockado e retorna handlers registrados."""
    mock_app = MagicMock()
    mock_app.bot = AsyncMock()
    with patch("telegram.ext.ApplicationBuilder") as mock_builder:
        mock_builder.return_value.token.return_value.build.return_value = mock_app
        await bus._ensure_app()
    return mock_app


def _make_update(chat_id=12345, user_id=67890, text="ola", thread_id=None):
    """Cria update mock padrao."""
    update = MagicMock()
    update.message.chat_id = chat_id
    update.message.chat.type = "supergroup"
    update.message.from_user.id = user_id
    update.message.message_thread_id = thread_id
    update.message.text = text
    update.message.entities = []
    update.message.voice = None
    update.message.photo = None
    update.message.document = None
    update.message.caption = None
    return update


# --- __init__ e start ---


class TestInit:
    """Testes para o construtor e valores iniciais."""

    def test_init_sem_token_le_env(self, monkeypatch):
        """Sem token, le do TELEGRAM_TOKEN."""
        monkeypatch.setenv("TELEGRAM_TOKEN", "env-token")
        b = TelegramMessageBus()
        assert b._token == "env-token"

    def test_init_sem_chat_id_le_env(self, monkeypatch):
        """Sem chat_id, le do TELEGRAM_CHAT_ID."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "99999")
        b = TelegramMessageBus(token="t")
        assert b._allowed_chat_id == "99999"

    def test_init_valores_padrao(self):
        """Verifica valores padrao do construtor."""
        b = TelegramMessageBus(token="t")
        assert b._activation_mode == "mention"
        assert b._bot_username == ""
        assert b._message_callback is None
        assert b._voice_callback is None
        assert b._photo_callback is None
        assert b._document_callback is None
        assert b._reaction_callback is None
        assert b._app is None
        assert b._pending_approvals == {}
        assert b._pending_text_reply == {}
        assert b._is_forum is False


# --- start() e stop() ---


class TestStartStop:
    """Testes para start e stop."""

    @pytest.mark.asyncio
    async def test_start_detecta_username(self, bus):
        """Verifica que start detecta username do bot."""
        mock_app = await _setup_app(bus)

        bot_info = MagicMock()
        bot_info.username = "testbot"
        mock_app.bot.get_me = AsyncMock(return_value=bot_info)
        mock_app.initialize = AsyncMock()
        mock_app.start = AsyncMock()
        mock_app.updater = MagicMock()
        mock_app.updater.start_polling = AsyncMock()

        with patch.object(bus, "_detect_forum_mode", new_callable=AsyncMock):
            await bus.start()

        assert bus._bot_username == "testbot"

    @pytest.mark.asyncio
    async def test_start_username_falha_nao_propaga(self, bus):
        """Verifica que erro ao obter username nao propaga."""
        mock_app = await _setup_app(bus)
        mock_app.bot.get_me = AsyncMock(side_effect=Exception("API error"))
        mock_app.initialize = AsyncMock()
        mock_app.start = AsyncMock()
        mock_app.updater = MagicMock()
        mock_app.updater.start_polling = AsyncMock()

        with patch.object(bus, "_detect_forum_mode", new_callable=AsyncMock):
            await bus.start()
        assert bus._bot_username == ""

    @pytest.mark.asyncio
    async def test_stop_sem_app(self, bus):
        """Stop sem app nao falha."""
        bus._app = None
        await bus.stop()

    @pytest.mark.asyncio
    async def test_stop_com_app(self, bus):
        """Stop com app para polling e encerra."""
        mock_app = MagicMock()
        mock_app.updater.running = True
        mock_app.updater.stop = AsyncMock()
        mock_app.running = True
        mock_app.stop = AsyncMock()
        mock_app.shutdown = AsyncMock()
        bus._app = mock_app

        await bus.stop()

        mock_app.updater.stop.assert_called_once()
        mock_app.stop.assert_called_once()
        mock_app.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_updater_nao_rodando(self, bus):
        """Stop com updater nao rodando nao chama stop do updater."""
        mock_app = MagicMock()
        mock_app.updater.running = False
        mock_app.running = False
        mock_app.shutdown = AsyncMock()
        bus._app = mock_app

        await bus.stop()

        mock_app.shutdown.assert_called_once()


# --- _ensure_app e handlers ---


class TestEnsureAppImportError:
    """Testes para _ensure_app quando telegram nao esta instalado."""

    @pytest.mark.asyncio
    async def test_ensure_app_import_error(self, bus):
        """Verifica que ImportError é relancado com mensagem util."""
        with patch.dict("sys.modules", {"telegram.ext": None}):
            with patch("builtins.__import__", side_effect=ImportError("no telegram")):
                with pytest.raises(ImportError, match="python-telegram-bot"):
                    await bus._ensure_app()

    @pytest.mark.asyncio
    async def test_ensure_app_idempotente(self, bus):
        """Segunda chamada nao recria o app."""
        mock_app = await _setup_app(bus)
        first_app = bus._app

        # Chama novamente — deve ser noop
        await bus._ensure_app()
        assert bus._app is first_app


class TestEnsureAppReactionImportError:
    """Testes para MessageReactionHandler nao disponivel."""

    @pytest.mark.asyncio
    async def test_reaction_handler_indisponivel(self, bus):
        """Verifica log quando MessageReactionHandler nao existe."""
        mock_app = MagicMock()
        mock_app.bot = AsyncMock()

        with patch("telegram.ext.ApplicationBuilder") as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            with patch("telegram.ext.MessageReactionHandler", side_effect=ImportError):
                await bus._ensure_app()

        # App foi criado mesmo sem reaction handler
        assert bus._app is not None


# --- Handlers de texto com pending reply ---


class TestHandleTextPendingReply:
    """Testes para _handle_text com respostas pendentes."""

    @pytest.mark.asyncio
    async def test_pending_reply_com_thread(self, bus):
        """Mensagem resolve pending_text_reply com chave thread."""
        mock_app = await _setup_app(bus)
        text_handler = mock_app.add_handler.call_args_list[0][0][0]

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        bus._pending_text_reply["12345:42"] = future

        update = _make_update(text="minha resposta", thread_id=42)
        await text_handler.callback(update, MagicMock())

        assert future.result() == "minha resposta"

    @pytest.mark.asyncio
    async def test_pending_reply_fallback_sem_thread(self, bus):
        """Mensagem resolve pending_text_reply com chave sem thread."""
        mock_app = await _setup_app(bus)
        text_handler = mock_app.add_handler.call_args_list[0][0][0]

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        bus._pending_text_reply["12345"] = future

        update = _make_update(text="resposta fallback", thread_id=None)
        await text_handler.callback(update, MagicMock())

        assert future.result() == "resposta fallback"

    @pytest.mark.asyncio
    async def test_handle_text_sem_message(self, bus):
        """Update sem message retorna sem processar."""
        mock_app = await _setup_app(bus)
        text_handler = mock_app.add_handler.call_args_list[0][0][0]

        update = MagicMock()
        update.message = None

        await text_handler.callback(update, MagicMock())
        # Nenhum callback deve ser chamado

    @pytest.mark.asyncio
    async def test_handle_text_typing_falha_silenciosa(self, bus):
        """Erro ao enviar typing nao propaga."""
        mock_app = await _setup_app(bus)
        mock_app.bot.send_chat_action.side_effect = Exception("typing error")
        text_handler = mock_app.add_handler.call_args_list[0][0][0]

        callback = AsyncMock()
        bus._message_callback = callback

        update = _make_update(text="ola")
        await text_handler.callback(update, MagicMock())

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_text_should_process_false(self, bus):
        """Mensagem que nao passa _should_process e ignorada."""
        bus._activation_mode = "command"
        mock_app = await _setup_app(bus)
        text_handler = mock_app.add_handler.call_args_list[0][0][0]

        callback = AsyncMock()
        bus._message_callback = callback

        update = _make_update(text="texto sem barra")
        update.message.chat.type = "supergroup"
        await text_handler.callback(update, MagicMock())

        callback.assert_not_called()


# --- Handler de voz ---


class TestHandleVoice:
    """Testes para _handle_voice."""

    @pytest.mark.asyncio
    async def test_handle_voice_sem_message(self, bus):
        """Update sem message retorna sem processar."""
        mock_app = await _setup_app(bus)
        voice_handler = mock_app.add_handler.call_args_list[2][0][0]

        update = MagicMock()
        update.message = None
        await voice_handler.callback(update, MagicMock())

    @pytest.mark.asyncio
    async def test_handle_voice_sem_voice(self, bus):
        """Update sem voice retorna sem processar."""
        mock_app = await _setup_app(bus)
        voice_handler = mock_app.add_handler.call_args_list[2][0][0]

        update = MagicMock()
        update.message.voice = None
        await voice_handler.callback(update, MagicMock())

    @pytest.mark.asyncio
    async def test_handle_voice_nao_autorizado(self, bus):
        """Voz de chat nao autorizado e ignorada."""
        mock_app = await _setup_app(bus)
        voice_handler = mock_app.add_handler.call_args_list[2][0][0]

        callback = AsyncMock()
        bus._voice_callback = callback

        update = MagicMock()
        update.message.voice = MagicMock()
        update.message.chat_id = 99999
        update.message.from_user.id = 99999
        update.message.message_thread_id = None

        await voice_handler.callback(update, MagicMock())
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_voice_com_callback(self, bus):
        """Voz autorizada com callback transcreve e chama callback."""
        mock_app = await _setup_app(bus)
        voice_handler = mock_app.add_handler.call_args_list[2][0][0]

        callback = AsyncMock()
        bus._voice_callback = callback

        update = MagicMock()
        update.message.voice = MagicMock()
        update.message.chat_id = 12345
        update.message.from_user.id = 67890
        update.message.message_thread_id = None

        with patch.object(bus, "_transcribe_voice", new_callable=AsyncMock) as mock_trans:
            mock_trans.return_value = "texto transcrito"
            await voice_handler.callback(update, MagicMock())

        callback.assert_called_once_with(
            "texto transcrito", thread_id=None, user_id="67890"
        )

    @pytest.mark.asyncio
    async def test_handle_voice_transcricao_vazia(self, bus):
        """Voz com transcricao vazia nao chama callback."""
        mock_app = await _setup_app(bus)
        voice_handler = mock_app.add_handler.call_args_list[2][0][0]

        callback = AsyncMock()
        bus._voice_callback = callback

        update = MagicMock()
        update.message.voice = MagicMock()
        update.message.chat_id = 12345
        update.message.from_user.id = 67890
        update.message.message_thread_id = None

        with patch.object(bus, "_transcribe_voice", new_callable=AsyncMock) as mock_trans:
            mock_trans.return_value = None
            await voice_handler.callback(update, MagicMock())

        callback.assert_not_called()


# --- Handler de callback (botoes inline) ---


class TestHandleCallback:
    """Testes para _handle_callback."""

    @pytest.mark.asyncio
    async def test_handle_callback_resolve_approval(self, bus):
        """Callback resolve pending_approval."""
        mock_app = await _setup_app(bus)
        cb_handler = mock_app.add_handler.call_args_list[5][0][0]

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        bus._pending_approvals["12345:100"] = future

        update = MagicMock()
        update.callback_query.from_user.id = 67890
        update.callback_query.message.chat_id = 12345
        update.callback_query.message.message_id = 100
        update.callback_query.data = "Aprovar"
        update.callback_query.answer = AsyncMock()

        await cb_handler.callback(update, MagicMock())

        assert future.result() == "Aprovar"

    @pytest.mark.asyncio
    async def test_handle_callback_nao_autorizado(self, bus):
        """Callback de chat nao autorizado e ignorado."""
        mock_app = await _setup_app(bus)
        cb_handler = mock_app.add_handler.call_args_list[5][0][0]

        update = MagicMock()
        update.callback_query.from_user.id = 99999
        update.callback_query.message.chat_id = 99999
        update.callback_query.message.message_id = 100
        update.callback_query.data = "Aprovar"
        update.callback_query.answer = AsyncMock()

        await cb_handler.callback(update, MagicMock())

    @pytest.mark.asyncio
    async def test_handle_callback_sem_pending(self, bus):
        """Callback sem pending_approval nao falha."""
        mock_app = await _setup_app(bus)
        cb_handler = mock_app.add_handler.call_args_list[5][0][0]

        update = MagicMock()
        update.callback_query.from_user.id = 67890
        update.callback_query.message.chat_id = 12345
        update.callback_query.message.message_id = 200
        update.callback_query.data = "Cancelar"
        update.callback_query.answer = AsyncMock()

        await cb_handler.callback(update, MagicMock())


# --- Handler de foto ---


class TestHandlePhoto:
    """Testes para _handle_photo."""

    @pytest.mark.asyncio
    async def test_handle_photo_sem_message(self, bus):
        """Update sem message retorna sem processar."""
        mock_app = await _setup_app(bus)
        photo_handler = mock_app.add_handler.call_args_list[3][0][0]

        update = MagicMock()
        update.message = None
        await photo_handler.callback(update, MagicMock())

    @pytest.mark.asyncio
    async def test_handle_photo_sem_photo(self, bus):
        """Update sem photo retorna sem processar."""
        mock_app = await _setup_app(bus)
        photo_handler = mock_app.add_handler.call_args_list[3][0][0]

        update = MagicMock()
        update.message.photo = None
        await photo_handler.callback(update, MagicMock())

    @pytest.mark.asyncio
    async def test_handle_photo_nao_autorizado(self, bus):
        """Foto de chat nao autorizado e ignorada."""
        mock_app = await _setup_app(bus)
        photo_handler = mock_app.add_handler.call_args_list[3][0][0]

        callback = AsyncMock()
        bus._photo_callback = callback

        update = MagicMock()
        update.message.photo = [MagicMock()]
        update.message.chat_id = 99999
        update.message.from_user.id = 99999
        update.message.message_thread_id = None

        await photo_handler.callback(update, MagicMock())
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_photo_sem_callback(self, bus):
        """Foto sem callback registrado retorna sem processar."""
        mock_app = await _setup_app(bus)
        photo_handler = mock_app.add_handler.call_args_list[3][0][0]

        bus._photo_callback = None

        update = MagicMock()
        update.message.photo = [MagicMock()]
        update.message.chat_id = 12345
        update.message.from_user.id = 67890
        update.message.message_thread_id = None

        await photo_handler.callback(update, MagicMock())

    @pytest.mark.asyncio
    async def test_handle_photo_com_callback(self, bus):
        """Foto autorizada com callback baixa e chama callback."""
        mock_app = await _setup_app(bus)
        photo_handler = mock_app.add_handler.call_args_list[3][0][0]

        callback = AsyncMock()
        bus._photo_callback = callback

        photo_mock = AsyncMock()
        file_mock = AsyncMock()
        file_mock.download_to_drive = AsyncMock()
        photo_mock.get_file.return_value = file_mock

        update = MagicMock()
        update.message.photo = [photo_mock]
        update.message.chat_id = 12345
        update.message.from_user.id = 67890
        update.message.message_thread_id = 42
        update.message.caption = "Minha foto"

        await photo_handler.callback(update, MagicMock())

        callback.assert_called_once()
        call_args = callback.call_args
        assert call_args[0][0] == "Minha foto"
        assert call_args[1]["thread_id"] == "42"
        assert call_args[1]["user_id"] == "67890"

    @pytest.mark.asyncio
    async def test_handle_photo_sem_caption(self, bus):
        """Foto sem caption usa default."""
        mock_app = await _setup_app(bus)
        photo_handler = mock_app.add_handler.call_args_list[3][0][0]

        callback = AsyncMock()
        bus._photo_callback = callback

        photo_mock = AsyncMock()
        file_mock = AsyncMock()
        file_mock.download_to_drive = AsyncMock()
        photo_mock.get_file.return_value = file_mock

        update = MagicMock()
        update.message.photo = [photo_mock]
        update.message.chat_id = 12345
        update.message.from_user.id = 67890
        update.message.message_thread_id = None
        update.message.caption = None

        await photo_handler.callback(update, MagicMock())

        assert callback.call_args[0][0] == "Analise esta imagem"


# --- Handler de documento ---


class TestHandleDocument:
    """Testes para _handle_document."""

    @pytest.mark.asyncio
    async def test_handle_document_sem_message(self, bus):
        """Update sem message retorna sem processar."""
        mock_app = await _setup_app(bus)
        doc_handler = mock_app.add_handler.call_args_list[4][0][0]

        update = MagicMock()
        update.message = None
        await doc_handler.callback(update, MagicMock())

    @pytest.mark.asyncio
    async def test_handle_document_sem_document(self, bus):
        """Update sem document retorna sem processar."""
        mock_app = await _setup_app(bus)
        doc_handler = mock_app.add_handler.call_args_list[4][0][0]

        update = MagicMock()
        update.message.document = None
        await doc_handler.callback(update, MagicMock())

    @pytest.mark.asyncio
    async def test_handle_document_nao_autorizado(self, bus):
        """Documento de chat nao autorizado e ignorado."""
        mock_app = await _setup_app(bus)
        doc_handler = mock_app.add_handler.call_args_list[4][0][0]

        callback = AsyncMock()
        bus._document_callback = callback

        update = MagicMock()
        update.message.document = MagicMock()
        update.message.chat_id = 99999
        update.message.from_user.id = 99999
        update.message.message_thread_id = None

        await doc_handler.callback(update, MagicMock())
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_document_sem_callback(self, bus):
        """Documento sem callback registrado retorna sem processar."""
        mock_app = await _setup_app(bus)
        doc_handler = mock_app.add_handler.call_args_list[4][0][0]

        bus._document_callback = None

        update = MagicMock()
        update.message.document = MagicMock()
        update.message.chat_id = 12345
        update.message.from_user.id = 67890
        update.message.message_thread_id = None

        await doc_handler.callback(update, MagicMock())

    @pytest.mark.asyncio
    async def test_handle_document_com_callback(self, bus):
        """Documento autorizado com callback baixa e chama callback."""
        mock_app = await _setup_app(bus)
        doc_handler = mock_app.add_handler.call_args_list[4][0][0]

        callback = AsyncMock()
        bus._document_callback = callback

        doc_mock = AsyncMock()
        doc_mock.file_name = "relatorio.pdf"
        file_mock = AsyncMock()
        file_mock.download_to_drive = AsyncMock()
        doc_mock.get_file.return_value = file_mock

        update = MagicMock()
        update.message.document = doc_mock
        update.message.chat_id = 12345
        update.message.from_user.id = 67890
        update.message.message_thread_id = None
        update.message.caption = "Relatorio Q4"

        await doc_handler.callback(update, MagicMock())

        callback.assert_called_once()
        call_args = callback.call_args
        assert call_args[0][0] == "Relatorio Q4"
        assert call_args[1]["original_filename"] == "relatorio.pdf"

    @pytest.mark.asyncio
    async def test_handle_document_sem_nome(self, bus):
        """Documento sem file_name gera nome generico."""
        mock_app = await _setup_app(bus)
        doc_handler = mock_app.add_handler.call_args_list[4][0][0]

        callback = AsyncMock()
        bus._document_callback = callback

        doc_mock = AsyncMock()
        doc_mock.file_name = None
        file_mock = AsyncMock()
        file_mock.download_to_drive = AsyncMock()
        doc_mock.get_file.return_value = file_mock

        update = MagicMock()
        update.message.document = doc_mock
        update.message.chat_id = 12345
        update.message.from_user.id = 67890
        update.message.message_thread_id = None
        update.message.caption = None

        await doc_handler.callback(update, MagicMock())

        callback.assert_called_once()
        # Caption default deve conter "Documento recebido"
        assert "Documento recebido" in callback.call_args[0][0]


# --- _transcribe_voice ---


class TestTranscribeVoice:
    """Testes para _transcribe_voice via whisper HTTP."""

    @pytest.mark.asyncio
    async def test_transcribe_excecao_retorna_none(self, bus):
        """Excecao na transcricao retorna None."""
        update = MagicMock()
        update.message.voice.file_id = "abc"
        context = MagicMock()
        context.bot.get_file = AsyncMock(side_effect=Exception("error"))

        result = await bus._transcribe_voice(update, context)
        assert result is None


# --- send_approval_request e ask_user ---


class TestApprovalAndAsk:
    """Testes para send_approval_request e ask_user."""

    @pytest.mark.asyncio
    async def test_ask_user_sem_pergunta(self, bus):
        """ask_user com pergunta vazia nao envia mensagem."""
        mock_app = MagicMock()
        mock_app.bot = AsyncMock()
        bus._app = mock_app

        async def _test():
            async def _respond():
                await asyncio.sleep(0.01)
                reply_key = "12345"
                if reply_key in bus._pending_text_reply:
                    bus._pending_text_reply[reply_key].set_result("ok")

            asyncio.create_task(_respond())
            return await bus.ask_user("12345", "")

        result = await _test()
        assert result == "ok"
        # send_message nao deve ser chamado para pergunta vazia
        # (o _send so e chamado se question)

    @pytest.mark.asyncio
    async def test_ask_user_com_thread(self, bus):
        """ask_user com thread_id usa chave combinada."""
        mock_app = MagicMock()
        mock_app.bot = AsyncMock()
        bus._app = mock_app

        async def _test():
            async def _respond():
                await asyncio.sleep(0.01)
                reply_key = "12345:42"
                if reply_key in bus._pending_text_reply:
                    bus._pending_text_reply[reply_key].set_result("resposta")

            asyncio.create_task(_respond())
            return await bus.ask_user("12345", "Pergunta", thread_id="42")

        result = await _test()
        assert result == "resposta"


# --- create_thread ---


class TestCreateThreadDeep:
    """Testes adicionais para create_thread."""

    @pytest.mark.asyncio
    async def test_create_thread_sem_app(self, bus):
        """create_thread sem app inicializa app."""
        bus._app = None
        with patch.object(bus, "_ensure_app", new_callable=AsyncMock):
            bus._app = MagicMock()
            bus._app.bot = AsyncMock()
            mock_result = MagicMock()
            mock_result.message_thread_id = 123
            bus._app.bot.create_forum_topic.return_value = mock_result

            result = await bus.create_thread("12345", "Titulo")
            assert result == "123"
