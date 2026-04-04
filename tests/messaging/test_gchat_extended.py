"""Testes estendidos para GChatMessageBus — cobertura de caminhos adicionais."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_squad.messaging.gchat import (
    DEFAULT_POLL_INTERVAL,
    MAX_MESSAGE_LENGTH,
    GChatMessageBus,
)


@pytest.fixture
def bus(monkeypatch):
    """Cria instancia de GChatMessageBus com env vars mockadas."""
    monkeypatch.setenv("GCHAT_CREDENTIALS_PATH", "/fake/creds.json")
    monkeypatch.setenv("GCHAT_SPACE_ID", "spaces/AAAA123")
    return GChatMessageBus(persona_name="Squad", persona_avatar="🤖", activation_mode="all")


# --- Constantes ---


class TestConstantes:
    """Testes para constantes do modulo."""

    def test_default_poll_interval(self):
        """Verifica valor padrao do intervalo de polling."""
        assert DEFAULT_POLL_INTERVAL == 3

    def test_max_message_length(self):
        """Verifica tamanho maximo de mensagem."""
        assert MAX_MESSAGE_LENGTH == 4096


# --- Construtor ---


class TestConstrutor:
    """Testes para o construtor do GChatMessageBus."""

    def test_valores_padrao(self, monkeypatch):
        """Verifica valores padrao do construtor."""
        monkeypatch.setenv("GCHAT_CREDENTIALS_PATH", "/fake")
        monkeypatch.setenv("GCHAT_SPACE_ID", "spaces/X")
        b = GChatMessageBus()
        assert b._persona_name == "Agent"
        assert b._persona_avatar == ""
        assert b._activation_mode == "mention"
        assert b._service is None
        assert b._bot_id == ""
        assert b._is_oauth is False
        assert b._running is False
        assert b._last_seen == ""
        assert b._message_callback is None

    def test_poll_interval_custom(self, monkeypatch):
        """Verifica que GCHAT_POLL_INTERVAL e lido do env."""
        monkeypatch.setenv("GCHAT_CREDENTIALS_PATH", "/fake")
        monkeypatch.setenv("GCHAT_SPACE_ID", "spaces/X")
        monkeypatch.setenv("GCHAT_POLL_INTERVAL", "10")
        b = GChatMessageBus()
        assert b._poll_interval == 10


# --- _format_space ---


class TestFormatSpace:
    """Testes para _format_space."""

    def test_com_prefixo(self, bus):
        """Space ID com prefixo permanece inalterado."""
        assert bus._format_space() == "spaces/AAAA123"

    def test_sem_prefixo(self, monkeypatch):
        """Space ID sem prefixo recebe 'spaces/'."""
        monkeypatch.setenv("GCHAT_CREDENTIALS_PATH", "/fake")
        monkeypatch.setenv("GCHAT_SPACE_ID", "BBBB456")
        b = GChatMessageBus()
        assert b._format_space() == "spaces/BBBB456"


# --- _should_process_msg ---


class TestShouldProcessMsg:
    """Testes para _should_process_msg."""

    def test_modo_all_processa_tudo(self, bus):
        """Modo 'all' processa qualquer mensagem."""
        msg = {"text": "ola", "thread": {"name": ""}}
        assert bus._should_process_msg(msg) is True

    def test_modo_command_com_barra(self, monkeypatch):
        """Modo 'command' processa mensagens com /."""
        monkeypatch.setenv("GCHAT_CREDENTIALS_PATH", "/fake")
        monkeypatch.setenv("GCHAT_SPACE_ID", "spaces/X")
        b = GChatMessageBus(activation_mode="command")
        msg = {"text": "/help", "thread": {"name": ""}}
        assert b._should_process_msg(msg) is True

    def test_modo_command_sem_barra(self, monkeypatch):
        """Modo 'command' ignora mensagens sem /."""
        monkeypatch.setenv("GCHAT_CREDENTIALS_PATH", "/fake")
        monkeypatch.setenv("GCHAT_SPACE_ID", "spaces/X")
        b = GChatMessageBus(activation_mode="command")
        msg = {"text": "ola", "thread": {"name": ""}}
        assert b._should_process_msg(msg) is False

    def test_modo_mention_com_bot_mention(self, monkeypatch):
        """Modo 'mention' com mencao ao bot processa."""
        monkeypatch.setenv("GCHAT_CREDENTIALS_PATH", "/fake")
        monkeypatch.setenv("GCHAT_SPACE_ID", "spaces/X")
        b = GChatMessageBus(activation_mode="mention")
        msg = {
            "text": "@bot ola",
            "thread": {"name": ""},
            "annotations": [
                {"type": "USER_MENTION", "userMention": {"type": "BOT"}},
            ],
        }
        assert b._should_process_msg(msg) is True

    def test_modo_mention_sem_mencao(self, monkeypatch):
        """Modo 'mention' sem mencao ao bot ignora."""
        monkeypatch.setenv("GCHAT_CREDENTIALS_PATH", "/fake")
        monkeypatch.setenv("GCHAT_SPACE_ID", "spaces/X")
        b = GChatMessageBus(activation_mode="mention")
        msg = {"text": "ola", "thread": {"name": ""}, "annotations": []}
        assert b._should_process_msg(msg) is False

    def test_pending_reply_sempre_processa(self, bus):
        """Mensagem com pending_reply e sempre processada."""
        bus._activation_mode = "mention"
        loop = asyncio.new_event_loop()
        bus._pending_text_reply["spaces/AAAA123"] = loop.create_future()
        msg = {"text": "resposta", "thread": {"name": ""}}
        assert bus._should_process_msg(msg) is True
        bus._pending_text_reply["spaces/AAAA123"].cancel()
        loop.close()

    def test_pending_reply_com_thread(self, bus):
        """Pending reply com thread_id."""
        bus._activation_mode = "mention"
        loop = asyncio.new_event_loop()
        bus._pending_text_reply["spaces/AAAA123:spaces/X/threads/T1"] = loop.create_future()
        msg = {"text": "resposta", "thread": {"name": "spaces/X/threads/T1"}}
        assert bus._should_process_msg(msg) is True
        bus._pending_text_reply["spaces/AAAA123:spaces/X/threads/T1"].cancel()
        loop.close()


# --- is_mention ---


class TestIsMention:
    """Testes para is_mention."""

    def test_sem_annotations(self, bus):
        """Sem annotations retorna False."""
        assert bus.is_mention({"annotations": []}) is False

    def test_bot_mention(self, bus):
        """Mencao tipo BOT retorna True."""
        msg = {
            "annotations": [
                {"type": "USER_MENTION", "userMention": {"type": "BOT"}},
            ],
        }
        assert bus.is_mention(msg) is True

    def test_oauth_mention_por_email(self, bus):
        """Mencao ao usuario autenticado por email retorna True."""
        bus._is_oauth = True
        bus._authenticated_user_id = "user@example.com"
        msg = {
            "annotations": [
                {
                    "type": "USER_MENTION",
                    "userMention": {
                        "type": "HUMAN",
                        "user": {"email": "user@example.com"},
                    },
                },
            ],
        }
        assert bus.is_mention(msg) is True

    def test_oauth_mention_por_name(self, bus):
        """Mencao ao usuario autenticado por name retorna True."""
        bus._is_oauth = True
        bus._authenticated_user_id = "users/123"
        msg = {
            "annotations": [
                {
                    "type": "USER_MENTION",
                    "userMention": {
                        "type": "HUMAN",
                        "user": {"name": "users/123"},
                    },
                },
            ],
        }
        assert bus.is_mention(msg) is True

    def test_mention_outro_usuario(self, bus):
        """Mencao a outro usuario retorna False."""
        msg = {
            "annotations": [
                {
                    "type": "USER_MENTION",
                    "userMention": {
                        "type": "HUMAN",
                        "user": {"email": "outro@example.com"},
                    },
                },
            ],
        }
        assert bus.is_mention(msg) is False


# --- is_dm ---


class TestIsDm:
    """Testes para is_dm."""

    def test_dm(self, bus):
        """DM retorna True."""
        assert bus.is_dm({"space_type": "DIRECT_MESSAGE"}) is True

    def test_nao_dm(self, bus):
        """Espaco nao-DM retorna False."""
        assert bus.is_dm({"space_type": "SPACE"}) is False

    def test_sem_space_type(self, bus):
        """Sem space_type retorna False."""
        assert bus.is_dm({}) is False


# --- register_personas ---


class TestRegisterPersonas:
    """Testes para register_personas."""

    def test_registra_prefixos(self, bus):
        """Verifica que prefixos de persona sao registrados."""
        po = MagicMock()
        po.avatar = "📋"
        po.name = "PO Agent"
        dev = MagicMock()
        dev.avatar = "⚙️"
        dev.name = "Dev Backend"
        personas = {"po": po, "dev": dev}
        bus.register_personas(personas)

        assert "📋 PO Agent" in bus._own_prefixes
        assert "⚙️ Dev Backend" in bus._own_prefixes

    def test_inclui_prefixo_do_bus(self, bus):
        """Verifica que prefixo do proprio bus e incluido."""
        bus.register_personas({})
        assert "🤖 Squad" in bus._own_prefixes

    def test_nao_duplica_prefixo_bus(self, bus):
        """Verifica que prefixo do bus nao e duplicado."""
        personas = {
            "squad": MagicMock(avatar="🤖", name="Squad"),
        }
        bus.register_personas(personas)
        count = bus._own_prefixes.count("🤖 Squad")
        assert count == 1


# --- _process_message ---


class TestProcessMessage:
    """Testes para _process_message."""

    @pytest.mark.asyncio
    async def test_ignora_mensagem_do_bot(self, bus):
        """Mensagens do bot sao ignoradas."""
        bus._message_callback = AsyncMock()
        msg = {
            "createTime": "2026-01-01T00:00:00Z",
            "sender": {"type": "BOT"},
            "text": "msg do bot",
            "thread": {"name": ""},
        }
        await bus._process_message(msg)
        bus._message_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignora_texto_vazio(self, bus):
        """Mensagens vazias sao ignoradas."""
        bus._message_callback = AsyncMock()
        msg = {
            "createTime": "2026-01-01T00:00:01Z",
            "sender": {"type": "HUMAN", "name": "users/1"},
            "text": "   ",
            "thread": {"name": ""},
        }
        await bus._process_message(msg)
        bus._message_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignora_propria_mensagem_oauth(self, bus):
        """No modo OAuth, ignora mensagens com prefixo de persona."""
        bus._is_oauth = True
        bus._own_prefixes = ["🤖 Squad"]
        bus._message_callback = AsyncMock()
        msg = {
            "createTime": "2026-01-01T00:00:02Z",
            "sender": {"type": "HUMAN", "name": "users/1"},
            "text": "🤖 Squad\n\nMensagem do agente",
            "thread": {"name": ""},
        }
        await bus._process_message(msg)
        bus._message_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_pending_reply(self, bus):
        """Resolve pending_reply quando existe."""
        future = asyncio.get_event_loop().create_future()
        bus._pending_text_reply["spaces/AAAA123"] = future
        msg = {
            "createTime": "2026-01-01T00:00:03Z",
            "sender": {"type": "HUMAN", "name": "users/1"},
            "text": "minha resposta",
            "thread": {"name": ""},
        }
        await bus._process_message(msg)
        assert future.result() == "minha resposta"

    @pytest.mark.asyncio
    async def test_resolve_pending_reply_com_thread(self, bus):
        """Resolve pending_reply com thread_id."""
        key = "spaces/AAAA123:spaces/X/threads/T1"
        future = asyncio.get_event_loop().create_future()
        bus._pending_text_reply[key] = future
        msg = {
            "createTime": "2026-01-01T00:00:04Z",
            "sender": {"type": "HUMAN", "name": "users/1"},
            "text": "resposta na thread",
            "thread": {"name": "spaces/X/threads/T1"},
        }
        await bus._process_message(msg)
        assert future.result() == "resposta na thread"

    @pytest.mark.asyncio
    async def test_atualiza_last_seen(self, bus):
        """Verifica que last_seen e atualizado."""
        msg = {
            "createTime": "2026-12-31T23:59:59Z",
            "sender": {"type": "BOT"},
            "text": "msg",
            "thread": {"name": ""},
        }
        await bus._process_message(msg)
        assert bus._last_seen == "2026-12-31T23:59:59Z"


# --- _fetch_new_messages ---


class TestFetchNewMessages:
    """Testes para _fetch_new_messages."""

    def test_sem_service_retorna_vazio(self, bus):
        """Sem service retorna lista vazia."""
        bus._service = None
        assert bus._fetch_new_messages() == []

    def test_com_last_seen_filtra(self, bus):
        """Com last_seen, adiciona filtro de createTime."""
        mock_service = MagicMock()
        mock_service.spaces().messages().list().execute.return_value = {
            "messages": [],
        }
        bus._service = mock_service
        bus._last_seen = "2026-01-01T00:00:00Z"

        bus._fetch_new_messages()

        call_kwargs = mock_service.spaces().messages().list.call_args[1]
        assert "filter" in call_kwargs

    def test_excecao_retorna_vazio(self, bus):
        """Excecao na API retorna lista vazia."""
        mock_service = MagicMock()
        mock_service.spaces().messages().list().execute.side_effect = Exception("API error")
        bus._service = mock_service

        result = bus._fetch_new_messages()
        assert result == []

    def test_ordena_por_create_time(self, bus):
        """Mensagens sao ordenadas por createTime."""
        mock_service = MagicMock()
        mock_service.spaces().messages().list().execute.return_value = {
            "messages": [
                {"createTime": "2026-01-02T00:00:00Z", "text": "segunda"},
                {"createTime": "2026-01-01T00:00:00Z", "text": "primeira"},
            ],
        }
        bus._service = mock_service

        result = bus._fetch_new_messages()
        assert result[0]["text"] == "primeira"
        assert result[1]["text"] == "segunda"


# --- send_message com split ---


class TestSendMessageSplit:
    """Testes para split de mensagens longas."""

    @pytest.mark.asyncio
    async def test_mensagem_longa_split(self, bus):
        """Mensagem maior que MAX_MESSAGE_LENGTH e dividida."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute = MagicMock(
            return_value={"name": "spaces/X/messages/1"}
        )
        bus._service = mock_service

        texto_longo = "x" * 5000
        await bus.send_message("spaces/AAAA123", texto_longo)

        # Deve chamar create pelo menos 2 vezes (prefixo + texto longo)
        assert mock_service.spaces().messages().create.call_count >= 2

    @pytest.mark.asyncio
    async def test_mensagem_com_sender_override(self, bus):
        """Sender override altera prefixo."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute = MagicMock(
            return_value={"name": "spaces/X/messages/1"}
        )
        bus._service = mock_service

        await bus.send_message("spaces/X", "texto", sender="👨‍💼 Lead")

        call_kwargs = mock_service.spaces().messages().create.call_args[1]
        assert "👨‍💼 Lead" in call_kwargs["body"]["text"]


# --- receive_message / receive_voice ---


class TestCallbacks:
    """Testes para registro de callbacks."""

    @pytest.mark.asyncio
    async def test_receive_message(self, bus):
        """Registra callback de mensagem."""
        cb = AsyncMock()
        await bus.receive_message(cb)
        assert bus._message_callback is cb

    @pytest.mark.asyncio
    async def test_receive_voice(self, bus):
        """Registra callback de voz (no-op)."""
        cb = AsyncMock()
        await bus.receive_voice(cb)
        assert bus._voice_callback is cb


# --- stop ---


class TestStop:
    """Testes para stop."""

    @pytest.mark.asyncio
    async def test_stop_cancela_poll_task(self, bus):
        """Verifica que stop cancela a poll task."""
        bus._running = True
        bus._poll_task = asyncio.create_task(asyncio.sleep(100))

        await bus.stop()

        assert bus._running is False
        assert bus._poll_task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_sem_poll_task(self, bus):
        """Verifica que stop funciona sem poll task."""
        bus._running = True
        bus._poll_task = None

        await bus.stop()

        assert bus._running is False


# --- bot_identifier ---


class TestBotIdentifier:
    """Testes para bot_identifier."""

    def test_retorna_bot_id(self, bus):
        """Retorna bot_id."""
        bus._bot_id = "bot123"
        assert bus.bot_identifier == "bot123"

    def test_bot_id_vazio(self, bus):
        """Bot ID vazio."""
        assert bus.bot_identifier == ""
