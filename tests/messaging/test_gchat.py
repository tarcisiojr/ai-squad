"""Testes para GChatMessageBus com mocks de API Google."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.messaging.gchat import GChatMessageBus
from src.messaging.interface import MessageBus


@pytest.fixture
def bus(monkeypatch):
    """Cria instância de GChatMessageBus com env vars mockadas."""
    monkeypatch.setenv("GCHAT_CREDENTIALS_PATH", "/fake/creds.json")
    monkeypatch.setenv("GCHAT_SPACE_ID", "spaces/AAAA123")
    return GChatMessageBus(persona_name="Squad", persona_avatar="🤖")


class TestGChatMessageBus:
    """Testes para GChatMessageBus."""

    def test_herda_message_bus(self, bus):
        """Verifica que GChatMessageBus implementa MessageBus."""
        assert isinstance(bus, MessageBus)

    def test_required_env_vars(self):
        """Verifica variáveis obrigatórias."""
        env_vars = GChatMessageBus.required_env_vars()
        assert "GCHAT_CREDENTIALS_PATH" in env_vars
        assert "GCHAT_SPACE_ID" in env_vars

    def test_env_template(self):
        """Verifica template de .env."""
        template = GChatMessageBus.env_template()
        assert "GCHAT_CREDENTIALS_PATH" in template
        assert "GCHAT_SPACE_ID" in template
        assert "PREENCHA_AQUI" in template

    def test_default_chat_id(self, bus):
        """Verifica que default_chat_id retorna space_id."""
        assert bus.default_chat_id == "spaces/AAAA123"

    def test_supports_threads(self, bus):
        """Google Chat Spaces sempre suportam threads."""
        assert bus.supports_threads is True

    def test_persona_configurada(self, bus):
        """Verifica configuração de persona."""
        assert bus._persona_name == "Squad"
        assert bus._persona_avatar == "🤖"

    def test_format_space_com_prefixo(self, bus):
        """Space ID com prefixo 'spaces/' permanece inalterado."""
        assert bus._format_space() == "spaces/AAAA123"

    def test_format_space_sem_prefixo(self, monkeypatch):
        """Space ID sem prefixo recebe 'spaces/' automaticamente."""
        monkeypatch.setenv("GCHAT_CREDENTIALS_PATH", "/fake/creds.json")
        monkeypatch.setenv("GCHAT_SPACE_ID", "AAAA123")
        b = GChatMessageBus()
        assert b._format_space() == "spaces/AAAA123"


class TestGChatSendMessage:
    """Testes para envio de mensagens."""

    @pytest.fixture
    def bus_with_service(self, bus):
        """Bus com service mockado."""
        mock_service = MagicMock()
        mock_execute = MagicMock(return_value={"name": "spaces/X/messages/1"})
        mock_service.spaces().messages().create().execute = mock_execute
        bus._service = mock_service
        return bus, mock_service

    @pytest.mark.asyncio
    async def test_send_message_texto_simples(self, bus_with_service):
        """Verifica envio de mensagem com prefixo de persona."""
        bus, service = bus_with_service

        await bus.send_message("spaces/AAAA123", "Olá!")

        service.spaces().messages().create.assert_called()
        call_kwargs = service.spaces().messages().create.call_args[1]
        assert call_kwargs["parent"] == "spaces/AAAA123"
        assert "Olá!" in call_kwargs["body"]["text"]
        assert "Squad" in call_kwargs["body"]["text"]

    @pytest.mark.asyncio
    async def test_send_message_com_thread_id(self, bus_with_service):
        """Verifica que thread_id é propagado como thread name."""
        bus, service = bus_with_service

        await bus.send_message("spaces/AAAA123", "Na thread", thread_id="spaces/X/threads/T1")

        call_kwargs = service.spaces().messages().create.call_args[1]
        assert call_kwargs["body"]["thread"]["name"] == "spaces/X/threads/T1"
        assert call_kwargs["messageReplyOption"] == "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"

    @pytest.mark.asyncio
    async def test_send_message_sem_thread(self, bus_with_service):
        """Verifica que sem thread_id não envia thread."""
        bus, service = bus_with_service

        await bus.send_message("spaces/AAAA123", "Geral")

        call_kwargs = service.spaces().messages().create.call_args[1]
        assert "thread" not in call_kwargs["body"]

    @pytest.mark.asyncio
    async def test_notify_com_emoji(self, bus_with_service):
        """Verifica que notify adiciona emoji de notificação."""
        bus, service = bus_with_service

        await bus.notify("spaces/AAAA123", "Tarefa concluída")

        call_kwargs = service.spaces().messages().create.call_args[1]
        assert "🔔" in call_kwargs["body"]["text"]
        assert "Tarefa concluída" in call_kwargs["body"]["text"]


class TestGChatApproval:
    """Testes para aprovações."""

    @pytest.mark.asyncio
    async def test_send_approval_request_envia_card(self, bus, monkeypatch):
        """Verifica que approval envia Card v2."""
        mock_service = MagicMock()
        mock_execute = MagicMock(return_value={"name": "spaces/X/messages/1"})
        mock_service.spaces().messages().create().execute = mock_execute
        bus._service = mock_service

        # Simula resposta "1" do usuário
        async def fake_reply():
            await asyncio.sleep(0.05)
            for key, future in bus._pending_text_reply.items():
                future.set_result("1")
                break

        task = asyncio.create_task(fake_reply())

        result = await bus.send_approval_request(
            "spaces/AAAA123", "Aprovar?", ["Aprovar", "Rejeitar"]
        )

        await task
        assert result == "Aprovar"

        # Verifica que foi enviado com cardsV2
        call_kwargs = mock_service.spaces().messages().create.call_args[1]
        assert "cardsV2" in call_kwargs["body"]


class TestGChatPolling:
    """Testes para polling de mensagens."""

    @pytest.mark.asyncio
    async def test_process_message_ignora_bot(self, bus):
        """Verifica que mensagens do bot são ignoradas."""
        msg = {
            "createTime": "2026-01-01T00:00:00Z",
            "sender": {"type": "BOT", "name": "users/bot123"},
            "text": "Mensagem do bot",
            "thread": {"name": ""},
        }

        bus._message_callback = AsyncMock()
        await bus._process_message(msg)

        bus._message_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_chama_callback(self, bus):
        """Verifica que mensagens humanas chamam o callback."""
        msg = {
            "createTime": "2026-01-01T00:00:01Z",
            "sender": {"type": "HUMAN", "name": "users/user456"},
            "text": "Criar API",
            "thread": {"name": "spaces/X/threads/T1"},
        }

        bus._message_callback = AsyncMock()
        await bus._process_message(msg)

        bus._message_callback.assert_called_once_with(
            "Criar API",
            thread_id="spaces/X/threads/T1",
            user_id="users/user456",
        )

    @pytest.mark.asyncio
    async def test_process_message_atualiza_last_seen(self, bus):
        """Verifica que last_seen é atualizado."""
        msg = {
            "createTime": "2026-01-01T12:00:00Z",
            "sender": {"type": "BOT"},
            "text": "algo",
            "thread": {"name": ""},
        }

        await bus._process_message(msg)

        assert bus._last_seen == "2026-01-01T12:00:00Z"

    @pytest.mark.asyncio
    async def test_process_message_ignora_vazio(self, bus):
        """Verifica que mensagens vazias são ignoradas."""
        msg = {
            "createTime": "2026-01-01T00:00:02Z",
            "sender": {"type": "HUMAN", "name": "users/user456"},
            "text": "",
            "thread": {"name": ""},
        }

        bus._message_callback = AsyncMock()
        await bus._process_message(msg)

        bus._message_callback.assert_not_called()


class TestGChatThread:
    """Testes para threads."""

    @pytest.mark.asyncio
    async def test_create_thread_retorna_string(self, bus):
        """Verifica que create_thread retorna thread name como string."""
        mock_service = MagicMock()
        mock_execute = MagicMock(return_value={
            "thread": {"name": "spaces/AAAA123/threads/new-thread-123"},
        })
        mock_service.spaces().messages().create().execute = mock_execute
        bus._service = mock_service

        thread_id = await bus.create_thread("spaces/AAAA123", "Nova demanda")

        assert thread_id == "spaces/AAAA123/threads/new-thread-123"
        assert isinstance(thread_id, str)

    @pytest.mark.asyncio
    async def test_create_thread_falha_retorna_none(self, bus):
        """Verifica que falha retorna None."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute.side_effect = Exception("API error")
        bus._service = mock_service

        thread_id = await bus.create_thread("spaces/AAAA123", "Vai falhar")

        assert thread_id is None


class TestGChatRegistry:
    """Testes para registro no registry."""

    def test_gchat_registrado(self):
        """Verifica que gchat está registrado no registry."""
        from src.messaging.registry import get, load_builtin_providers

        load_builtin_providers()
        cls = get("gchat")
        assert cls is GChatMessageBus
