"""Testes estendidos para TelegramMessageBus — cobertura de caminhos adicionais."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_squad.messaging.telegram import TelegramMessageBus


@pytest.fixture
def bus():
    """Cria instancia de TelegramMessageBus."""
    return TelegramMessageBus(
        token="fake-token",
        persona_name="PO Agent",
        persona_avatar="📋",
        allowed_chat_id="12345",
        activation_mode="mention",
    )


# --- _escape_markdown_v2 ---


class TestEscapeMarkdownV2:
    """Testes para _escape_markdown_v2 — funcao pura, sem mocks."""

    def test_texto_simples_sem_especiais(self):
        """Texto sem caracteres especiais permanece inalterado."""
        assert TelegramMessageBus._escape_markdown_v2("Ola mundo") == "Ola mundo"

    def test_escapa_ponto(self):
        """Ponto deve ser escapado."""
        result = TelegramMessageBus._escape_markdown_v2("fim.")
        assert result == "fim\\."

    def test_escapa_exclamacao(self):
        """Exclamacao deve ser escapada."""
        result = TelegramMessageBus._escape_markdown_v2("Ola!")
        assert result == "Ola\\!"

    def test_escapa_parenteses(self):
        """Parenteses devem ser escapados."""
        result = TelegramMessageBus._escape_markdown_v2("func(x)")
        assert "\\(" in result
        assert "\\)" in result

    def test_escapa_colchetes(self):
        """Colchetes devem ser escapados."""
        result = TelegramMessageBus._escape_markdown_v2("arr[0]")
        assert "\\[" in result
        assert "\\]" in result

    def test_preserva_negrito(self):
        """Negrito (**texto**) deve ser preservado."""
        result = TelegramMessageBus._escape_markdown_v2("Isso e **importante**")
        assert "**importante**" in result

    def test_preserva_italico(self):
        """Italico (*texto*) deve ser preservado."""
        result = TelegramMessageBus._escape_markdown_v2("Isso e *enfase*")
        assert "*enfase*" in result

    def test_preserva_codigo(self):
        """Codigo (`texto`) deve ser preservado."""
        result = TelegramMessageBus._escape_markdown_v2("Use `pip install`")
        assert "`pip install`" in result

    def test_escapa_hifen(self):
        """Hifen deve ser escapado."""
        result = TelegramMessageBus._escape_markdown_v2("item - sub")
        assert "\\-" in result

    def test_escapa_til(self):
        """Til deve ser escapado."""
        result = TelegramMessageBus._escape_markdown_v2("~riscado~")
        assert "\\~" in result

    def test_escapa_maior_menor(self):
        """Maior que deve ser escapado."""
        result = TelegramMessageBus._escape_markdown_v2("> citacao")
        assert "\\>" in result

    def test_escapa_hash(self):
        """Hash deve ser escapado."""
        result = TelegramMessageBus._escape_markdown_v2("# titulo")
        assert "\\#" in result

    def test_escapa_igual(self):
        """Igual deve ser escapado."""
        result = TelegramMessageBus._escape_markdown_v2("a = b")
        assert "\\=" in result

    def test_escapa_pipe(self):
        """Pipe deve ser escapado."""
        result = TelegramMessageBus._escape_markdown_v2("a | b")
        assert "\\|" in result

    def test_escapa_chaves(self):
        """Chaves devem ser escapadas."""
        result = TelegramMessageBus._escape_markdown_v2("{key}")
        assert "\\{" in result
        assert "\\}" in result

    def test_multiplos_formatacoes(self):
        """Testa negrito + codigo + caracteres especiais."""
        result = TelegramMessageBus._escape_markdown_v2(
            "**negrito** e `codigo` com ponto."
        )
        assert "**negrito**" in result
        assert "`codigo`" in result
        assert "\\." in result


# --- _to_int_thread / _to_str_thread ---


class TestThreadConversion:
    """Testes para conversao de thread_id."""

    def test_to_int_thread_none(self, bus):
        """None retorna None."""
        assert bus._to_int_thread(None) is None

    def test_to_int_thread_valido(self, bus):
        """String numerica retorna int."""
        assert bus._to_int_thread("42") == 42

    def test_to_int_thread_invalido(self, bus):
        """String nao-numerica retorna None."""
        assert bus._to_int_thread("abc") is None

    def test_to_str_thread_none(self, bus):
        """None retorna None."""
        assert bus._to_str_thread(None) is None

    def test_to_str_thread_int(self, bus):
        """Int retorna str."""
        assert bus._to_str_thread(42) == "42"

    def test_to_str_thread_zero(self, bus):
        """Zero retorna '0'."""
        assert bus._to_str_thread(0) == "0"


# --- _is_authorized ---


class TestIsAuthorizedExtended:
    """Testes adicionais de autorizacao."""

    def test_is_authorized_match_exato(self, bus):
        """Chat ID autorizado retorna True."""
        assert bus._is_authorized("12345") is True

    def test_is_authorized_diferente(self, bus):
        """Chat ID diferente retorna False."""
        assert bus._is_authorized("99999") is False

    def test_is_authorized_sem_config(self):
        """Sem allowed_chat_id, rejeita tudo (fail-closed)."""
        b = TelegramMessageBus(token="t")
        assert b._is_authorized("12345") is False


# --- _should_process ---


class TestShouldProcess:
    """Testes para _should_process."""

    def test_sem_message_retorna_false(self, bus):
        """Update sem message retorna False."""
        update = MagicMock()
        update.message = None
        assert bus._should_process(update) is False

    def test_dm_sempre_processa(self, bus):
        """Mensagem privada (DM) sempre e processada."""
        update = MagicMock()
        update.message.chat.type = "private"
        assert bus._should_process(update) is True

    def test_modo_all_processa_grupo(self, bus):
        """Modo 'all' processa mensagens de grupo."""
        bus._activation_mode = "all"
        update = MagicMock()
        update.message.chat.type = "supergroup"
        update.message.chat_id = 12345
        update.message.message_thread_id = None
        assert bus._should_process(update) is True

    def test_modo_command_com_barra(self, bus):
        """Modo 'command' processa mensagens com /."""
        bus._activation_mode = "command"
        update = MagicMock()
        update.message.chat.type = "supergroup"
        update.message.chat_id = 12345
        update.message.message_thread_id = None
        update.message.text = "/start"
        assert bus._should_process(update) is True

    def test_modo_command_sem_barra(self, bus):
        """Modo 'command' ignora mensagens sem /."""
        bus._activation_mode = "command"
        update = MagicMock()
        update.message.chat.type = "supergroup"
        update.message.chat_id = 12345
        update.message.message_thread_id = None
        update.message.text = "ola"
        assert bus._should_process(update) is False

    def test_modo_mention_sem_username_processa_tudo(self, bus):
        """Sem bot_username, processa tudo."""
        bus._bot_username = ""
        bus._activation_mode = "mention"
        update = MagicMock()
        update.message.chat.type = "supergroup"
        update.message.chat_id = 12345
        update.message.message_thread_id = None
        update.message.entities = []
        update.message.text = "qualquer"
        assert bus._should_process(update) is True

    def test_modo_mention_com_mencao_correta(self, bus):
        """Com bot_username, processa quando mencionado."""
        bus._bot_username = "mybot"
        bus._activation_mode = "mention"
        entity = MagicMock()
        entity.type = "mention"
        entity.offset = 0
        entity.length = 6
        update = MagicMock()
        update.message.chat.type = "supergroup"
        update.message.chat_id = 12345
        update.message.message_thread_id = None
        update.message.entities = [entity]
        update.message.text = "@mybot ola"
        assert bus._should_process(update) is True

    def test_modo_mention_sem_mencao(self, bus):
        """Sem mencao ao bot, nao processa."""
        bus._bot_username = "mybot"
        bus._activation_mode = "mention"
        update = MagicMock()
        update.message.chat.type = "supergroup"
        update.message.chat_id = 12345
        update.message.message_thread_id = None
        update.message.entities = []
        update.message.text = "ola"
        assert bus._should_process(update) is False

    def test_modo_mention_com_bot_command(self, bus):
        """bot_command entity processa."""
        bus._bot_username = "mybot"
        bus._activation_mode = "mention"
        entity = MagicMock()
        entity.type = "bot_command"
        update = MagicMock()
        update.message.chat.type = "supergroup"
        update.message.chat_id = 12345
        update.message.message_thread_id = None
        update.message.entities = [entity]
        update.message.text = "/help"
        assert bus._should_process(update) is True

    def test_pending_reply_sempre_processa(self, bus):
        """Mensagem com pending reply sempre e processada."""
        bus._activation_mode = "mention"
        bus._bot_username = "mybot"
        loop = asyncio.new_event_loop()
        bus._pending_text_reply["12345"] = loop.create_future()
        update = MagicMock()
        update.message.chat.type = "supergroup"
        update.message.chat_id = 12345
        update.message.message_thread_id = None
        update.message.entities = []
        update.message.text = "resposta"
        assert bus._should_process(update) is True
        # Limpa future
        bus._pending_text_reply["12345"].cancel()
        loop.close()


# --- is_mention ---


class TestIsMention:
    """Testes para is_mention."""

    def test_sem_bot_username_retorna_true(self, bus):
        """Sem bot_username, nao filtra."""
        bus._bot_username = ""
        msg = {"entities": [], "text": "ola"}
        assert bus.is_mention(msg) is True

    def test_com_mencao_entity(self, bus):
        """Mencao via entity correta retorna True."""
        bus._bot_username = "mybot"
        msg = {
            "entities": [{"type": "mention", "offset": 0, "length": 6}],
            "text": "@mybot ola",
        }
        assert bus.is_mention(msg) is True

    def test_com_text_mention_entity(self, bus):
        """Mencao tipo text_mention retorna True."""
        bus._bot_username = "mybot"
        msg = {
            "entities": [{"type": "text_mention"}],
            "text": "ola",
        }
        assert bus.is_mention(msg) is True

    def test_sem_mencao_retorna_false(self, bus):
        """Sem mencao retorna False."""
        bus._bot_username = "mybot"
        msg = {"entities": [], "text": "ola"}
        assert bus.is_mention(msg) is False

    def test_mencao_de_outro_bot(self, bus):
        """Mencao a outro bot retorna False."""
        bus._bot_username = "mybot"
        msg = {
            "entities": [{"type": "mention", "offset": 0, "length": 9}],
            "text": "@otherbot ola",
        }
        assert bus.is_mention(msg) is False


# --- is_dm ---


class TestIsDm:
    """Testes para is_dm."""

    def test_chat_privado(self, bus):
        """Chat privado retorna True."""
        assert bus.is_dm({"chat_type": "private"}) is True

    def test_grupo(self, bus):
        """Grupo retorna False."""
        assert bus.is_dm({"chat_type": "supergroup"}) is False

    def test_sem_chat_type(self, bus):
        """Sem chat_type retorna False."""
        assert bus.is_dm({}) is False


# --- Propriedades ---


class TestPropriedades:
    """Testes para propriedades."""

    def test_default_chat_id(self, bus):
        """Retorna allowed_chat_id."""
        assert bus.default_chat_id == "12345"

    def test_supports_threads_default_false(self, bus):
        """Suporte a threads depende de _is_forum."""
        assert bus.supports_threads is False

    def test_supports_threads_quando_forum(self, bus):
        """Forum mode retorna True."""
        bus._is_forum = True
        assert bus.supports_threads is True

    def test_bot_identifier(self, bus):
        """Retorna bot_username."""
        bus._bot_username = "mybot"
        assert bus.bot_identifier == "mybot"

    def test_required_env_vars(self):
        """Verifica variaveis obrigatorias."""
        vars_ = TelegramMessageBus.required_env_vars()
        assert "TELEGRAM_TOKEN" in vars_
        assert "TELEGRAM_CHAT_ID" in vars_

    def test_env_template(self):
        """Verifica template de .env."""
        tmpl = TelegramMessageBus.env_template()
        assert "TELEGRAM_TOKEN" in tmpl
        assert "TELEGRAM_CHAT_ID" in tmpl


# --- _send (split de mensagens longas) ---


class TestSend:
    """Testes para _send."""

    @pytest.mark.asyncio
    async def test_send_mensagem_curta(self, bus):
        """Mensagem curta e enviada normalmente."""
        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus._send("12345", "curta")

        mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_mensagem_longa_split(self, bus):
        """Mensagem maior que 4096 e dividida em partes."""
        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        texto_longo = "x" * 5000
        await bus._send("12345", texto_longo)

        # Deve chamar send_message 2 vezes (4096 + 904)
        assert mock_bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_send_fallback_texto_plano(self, bus):
        """Se Markdown falha, envia texto plano."""
        mock_bot = AsyncMock()
        # Primeira chamada com Markdown falha, segunda sem parse_mode funciona
        mock_bot.send_message.side_effect = [Exception("parse error"), MagicMock()]
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus._send("12345", "texto com *problema")

        assert mock_bot.send_message.call_count == 2
        # Segunda chamada nao deve ter parse_mode
        second_call = mock_bot.send_message.call_args_list[1]
        assert "parse_mode" not in second_call[1]


# --- send_message com sender override ---


class TestSendMessageExtended:
    """Testes adicionais para send_message."""

    @pytest.mark.asyncio
    async def test_send_message_com_sender_override(self, bus):
        """Sender via kwargs tem prioridade sobre persona."""
        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus.send_message("12345", "texto", sender="👨‍💼 Lead")

        texto = mock_bot.send_message.call_args[1]["text"]
        assert "👨‍💼 Lead" in texto
        assert "PO Agent" not in texto

    @pytest.mark.asyncio
    async def test_send_message_sem_persona(self):
        """Sem persona, nao adiciona prefixo."""
        b = TelegramMessageBus(token="t", persona_name="", allowed_chat_id="1")
        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        b._app = mock_app

        await b.send_message("1", "texto puro")

        texto = mock_bot.send_message.call_args[1]["text"]
        assert texto == "texto puro"


# --- receive_photo / receive_document / on_reaction ---


class TestCallbacksExtended:
    """Testes para callbacks opcionais."""

    @pytest.mark.asyncio
    async def test_receive_photo_registra_callback(self, bus):
        """Verifica registro de callback de foto."""
        cb = AsyncMock()
        await bus.receive_photo(cb)
        assert bus._photo_callback is cb

    @pytest.mark.asyncio
    async def test_receive_document_registra_callback(self, bus):
        """Verifica registro de callback de documento."""
        cb = AsyncMock()
        await bus.receive_document(cb)
        assert bus._document_callback is cb

    @pytest.mark.asyncio
    async def test_on_reaction_registra_callback(self, bus):
        """Verifica registro de callback de reacao."""
        cb = AsyncMock()
        await bus.on_reaction(cb)
        assert bus._reaction_callback is cb


# --- send_photo ---


class TestSendPhoto:
    """Testes para send_photo."""

    @pytest.mark.asyncio
    async def test_send_photo_sucesso(self, bus, tmp_path):
        """Verifica envio de foto com sucesso."""
        foto = tmp_path / "test.jpg"
        foto.write_bytes(b"\xff\xd8\xff\xe0")

        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus.send_photo("12345", str(foto), caption="Teste")

        mock_bot.send_photo.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_photo_falha_fallback_texto(self, bus, tmp_path):
        """Verifica fallback para texto quando foto falha."""
        foto = tmp_path / "test.jpg"
        foto.write_bytes(b"\xff\xd8\xff\xe0")

        mock_bot = AsyncMock()
        mock_bot.send_photo.side_effect = Exception("erro upload")
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus.send_photo("12345", str(foto))

        # Deve ter enviado mensagem de fallback
        mock_bot.send_message.assert_called()


# --- send_typing ---


class TestSendTyping:
    """Testes para send_typing."""

    @pytest.mark.asyncio
    async def test_send_typing_com_thread(self, bus):
        """Verifica que send_typing propaga thread_id."""
        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus.send_typing("12345", thread_id="999")

        mock_bot.send_chat_action.assert_called_once_with(
            chat_id="12345",
            action="typing",
            message_thread_id=999,
        )

    @pytest.mark.asyncio
    async def test_send_typing_excecao_silenciosa(self, bus):
        """Verifica que send_typing nao propaga excecao."""
        mock_bot = AsyncMock()
        mock_bot.send_chat_action.side_effect = Exception("erro")
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus.send_typing("12345")  # nao deve lançar


# --- create_thread titulo longo ---


class TestCreateThreadExtended:
    """Testes adicionais para create_thread."""

    @pytest.mark.asyncio
    async def test_create_thread_trunca_titulo(self, bus):
        """Verifica que titulos longos sao truncados a 128 caracteres."""
        mock_bot = AsyncMock()
        mock_result = MagicMock()
        mock_result.message_thread_id = 42
        mock_bot.create_forum_topic.return_value = mock_result
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        titulo_longo = "A" * 200
        await bus.create_thread("12345", titulo_longo)

        call_kwargs = mock_bot.create_forum_topic.call_args[1]
        assert len(call_kwargs["name"]) == 128


# --- _detect_forum_mode ---


class TestDetectForumMode:
    """Testes para _detect_forum_mode."""

    @pytest.mark.asyncio
    async def test_detect_forum_true(self, bus):
        """Verifica deteccao de grupo-forum."""
        mock_bot = AsyncMock()
        mock_chat = MagicMock()
        mock_chat.is_forum = True
        mock_bot.get_chat.return_value = mock_chat
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus._detect_forum_mode()

        assert bus._is_forum is True

    @pytest.mark.asyncio
    async def test_detect_forum_false(self, bus):
        """Verifica deteccao de chat nao-forum."""
        mock_bot = AsyncMock()
        mock_chat = MagicMock()
        mock_chat.is_forum = False
        mock_bot.get_chat.return_value = mock_chat
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus._detect_forum_mode()

        assert bus._is_forum is False

    @pytest.mark.asyncio
    async def test_detect_forum_excecao(self, bus):
        """Verifica que excecao na deteccao define False."""
        mock_bot = AsyncMock()
        mock_bot.get_chat.side_effect = Exception("API error")
        mock_app = MagicMock()
        mock_app.bot = mock_bot
        bus._app = mock_app

        await bus._detect_forum_mode()

        assert bus._is_forum is False

    @pytest.mark.asyncio
    async def test_detect_forum_sem_app(self, bus):
        """Verifica que sem app nao falha."""
        bus._app = None
        await bus._detect_forum_mode()
        assert bus._is_forum is False

    @pytest.mark.asyncio
    async def test_detect_forum_sem_chat_id(self):
        """Verifica que sem chat_id nao faz deteccao."""
        b = TelegramMessageBus(token="t", allowed_chat_id="")
        b._app = MagicMock()
        await b._detect_forum_mode()
        assert b._is_forum is False
