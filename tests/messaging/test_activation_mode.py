"""Testes para filtro de activation_mode nos providers."""

from unittest.mock import AsyncMock, MagicMock, patch


class TestTelegramMention:
    """Testes de detecção de menção no Telegram."""

    def _make_bus(self, activation_mode="mention"):
        """Cria TelegramMessageBus com mocks."""
        from src.messaging.telegram import TelegramMessageBus

        bus = TelegramMessageBus(
            token="fake-token",
            allowed_chat_id="123",
            activation_mode=activation_mode,
        )
        bus._bot_username = "testbot"
        return bus

    def _make_update(self, text="hello", chat_type="supergroup", entities=None):
        """Cria mock de update do Telegram."""
        update = MagicMock()
        update.message.text = text
        update.message.chat.type = chat_type
        update.message.chat_id = 123
        update.message.message_thread_id = None
        update.message.entities = entities or []
        return update

    def test_dm_sempre_processa(self) -> None:
        """DM sempre é processado independente do activation_mode."""
        bus = self._make_bus(activation_mode="mention")
        update = self._make_update(chat_type="private")
        assert bus._should_process(update) is True

    def test_grupo_sem_mencao_ignora(self) -> None:
        """Grupo sem menção ignora em modo mention."""
        bus = self._make_bus(activation_mode="mention")
        update = self._make_update(text="mensagem normal")
        assert bus._should_process(update) is False

    def test_grupo_com_mencao_processa(self) -> None:
        """Grupo com menção @bot processa em modo mention."""
        bus = self._make_bus(activation_mode="mention")
        entity = MagicMock()
        entity.type = "mention"
        entity.offset = 0
        entity.length = 8
        update = self._make_update(text="@testbot ajuda", entities=[entity])
        assert bus._should_process(update) is True

    def test_modo_all_processa_tudo(self) -> None:
        """Modo all processa qualquer mensagem em grupo."""
        bus = self._make_bus(activation_mode="all")
        update = self._make_update(text="mensagem normal")
        assert bus._should_process(update) is True

    def test_modo_command_com_barra(self) -> None:
        """Modo command aceita mensagens com /."""
        bus = self._make_bus(activation_mode="command")
        update = self._make_update(text="/help")
        assert bus._should_process(update) is True

    def test_modo_command_sem_barra_ignora(self) -> None:
        """Modo command ignora mensagens sem /."""
        bus = self._make_bus(activation_mode="command")
        update = self._make_update(text="mensagem normal")
        assert bus._should_process(update) is False

    def test_pending_reply_ignora_filtro(self) -> None:
        """Pending reply sempre processa, mesmo sem menção."""
        bus = self._make_bus(activation_mode="mention")
        bus._pending_text_reply["123"] = MagicMock()
        update = self._make_update(text="resposta simples")
        assert bus._should_process(update) is True


class TestGChatMention:
    """Testes de detecção de menção no GChat."""

    def _make_bus(self, activation_mode="mention"):
        """Cria GChatMessageBus com mock."""
        from src.messaging.gchat import GChatMessageBus

        bus = GChatMessageBus(activation_mode=activation_mode)
        bus._space_id = "spaces/test"
        return bus

    def test_mencao_bot_detectada(self) -> None:
        """Detecta menção via annotations do GChat."""
        bus = self._make_bus()
        msg = {
            "text": "@bot ajuda",
            "annotations": [
                {"type": "USER_MENTION", "userMention": {"type": "BOT"}},
            ],
        }
        assert bus.is_mention(msg) is True

    def test_sem_mencao(self) -> None:
        """Mensagem sem menção não é detectada."""
        bus = self._make_bus()
        msg = {"text": "mensagem normal", "annotations": []}
        assert bus.is_mention(msg) is False

    def test_filtro_mention_ignora_sem_mencao(self) -> None:
        """Modo mention ignora mensagens sem menção."""
        bus = self._make_bus(activation_mode="mention")
        msg = {"text": "normal", "annotations": [], "thread": {}}
        assert bus._should_process_msg(msg) is False

    def test_filtro_all_processa_tudo(self) -> None:
        """Modo all processa tudo."""
        bus = self._make_bus(activation_mode="all")
        msg = {"text": "normal", "annotations": [], "thread": {}}
        assert bus._should_process_msg(msg) is True

    def test_pending_reply_ignora_filtro(self) -> None:
        """Pending reply sempre processa."""
        bus = self._make_bus(activation_mode="mention")
        bus._pending_text_reply["spaces/test"] = MagicMock()
        msg = {"text": "resposta", "annotations": [], "thread": {}}
        assert bus._should_process_msg(msg) is True
