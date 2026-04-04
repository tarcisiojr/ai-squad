"""Testes para métodos default da interface MessageBus."""

import pytest

from ai_squad.messaging.interface import MessageBus


class _ConcreteMinimalBus(MessageBus):
    """Implementação mínima para testar métodos default da interface."""

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    @classmethod
    def required_env_vars(cls) -> list[str]:
        return []

    @classmethod
    def env_template(cls) -> str:
        return ""

    async def send_message(self, user_id, text, **kwargs) -> None:
        pass

    async def send_approval_request(self, user_id, question, options, **kwargs) -> str:
        return options[0]

    async def ask_user(self, user_id, question, **kwargs) -> str:
        return ""

    async def receive_message(self, callback) -> None:
        pass

    async def receive_voice(self, callback) -> None:
        pass

    async def notify(self, user_id, text, **kwargs) -> None:
        pass


class TestMessageBusDefaults:
    """Testes para métodos default que retornam valores padrão."""

    def test_bot_identifier_vazio(self):
        """bot_identifier retorna string vazia por padrão."""
        bus = _ConcreteMinimalBus()
        assert bus.bot_identifier == ""

    def test_is_mention_true(self):
        """is_mention retorna True por padrão (sem filtro)."""
        bus = _ConcreteMinimalBus()
        assert bus.is_mention({}) is True

    def test_is_dm_false(self):
        """is_dm retorna False por padrão."""
        bus = _ConcreteMinimalBus()
        assert bus.is_dm({}) is False

    def test_supports_threads_false(self):
        """supports_threads retorna False por padrão."""
        bus = _ConcreteMinimalBus()
        assert bus.supports_threads is False

    def test_default_chat_id_vazio(self):
        """default_chat_id retorna string vazia por padrão."""
        bus = _ConcreteMinimalBus()
        assert bus.default_chat_id == ""

    @pytest.mark.asyncio
    async def test_send_photo_noop(self):
        """send_photo é no-op por padrão."""
        bus = _ConcreteMinimalBus()
        await bus.send_photo("user1", "/img.png", "caption")

    @pytest.mark.asyncio
    async def test_send_typing_noop(self):
        """send_typing é no-op por padrão."""
        bus = _ConcreteMinimalBus()
        await bus.send_typing("user1")

    @pytest.mark.asyncio
    async def test_run_forever_retorna_none(self):
        """run_forever retorna None por padrão."""
        bus = _ConcreteMinimalBus()
        result = await bus.run_forever()
        assert result is None

    def test_register_personas_noop(self):
        """register_personas é no-op por padrão."""
        bus = _ConcreteMinimalBus()
        bus.register_personas({"squad-lead": "leader"})

    @pytest.mark.asyncio
    async def test_create_thread_retorna_none(self):
        """create_thread retorna None por padrão."""
        bus = _ConcreteMinimalBus()
        result = await bus.create_thread("chat1", "Título")
        assert result is None

    @pytest.mark.asyncio
    async def test_receive_document_noop(self):
        """receive_document é no-op por padrão."""
        bus = _ConcreteMinimalBus()
        await bus.receive_document(lambda: None)

    @pytest.mark.asyncio
    async def test_on_reaction_noop(self):
        """on_reaction é no-op por padrão."""
        bus = _ConcreteMinimalBus()
        await bus.on_reaction(lambda: None)

    def test_mark_agent_active_noop(self):
        """mark_agent_active é no-op por padrão."""
        bus = _ConcreteMinimalBus()
        bus.mark_agent_active("Dev")

    def test_mark_agent_idle_noop(self):
        """mark_agent_idle é no-op por padrão."""
        bus = _ConcreteMinimalBus()
        bus.mark_agent_idle("Dev")
