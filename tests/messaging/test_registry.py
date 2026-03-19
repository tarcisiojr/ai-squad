"""Testes para o registry de providers de mensageria."""

import pytest

from src.messaging import registry
from src.messaging.interface import MessageBus


class FakeProvider(MessageBus):
    """Provider fake para testes do registry."""

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    @classmethod
    def required_env_vars(cls) -> list[str]:
        return ["FAKE_TOKEN"]

    @classmethod
    def env_template(cls) -> str:
        return "FAKE_TOKEN=placeholder\n"

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


class TestRegistry:
    """Testes para registro e resolução de providers."""

    def test_register_e_get(self):
        """Registra e resolve provider pelo nome."""
        registry.register("fake-test", FakeProvider)
        cls = registry.get("fake-test")
        assert cls is FakeProvider

    def test_get_provider_inexistente(self):
        """Erro ao resolver provider não registrado."""
        with pytest.raises(ValueError, match="não registrado"):
            registry.get("provider-que-nao-existe")

    def test_available_inclui_registrados(self):
        """Lista providers registrados."""
        registry.register("fake-avail", FakeProvider)
        names = registry.available()
        assert "fake-avail" in names

    def test_load_builtin_providers_registra_telegram_e_cli(self):
        """load_builtin_providers registra telegram e cli."""
        registry.load_builtin_providers()
        names = registry.available()
        assert "telegram" in names
        assert "cli" in names

    def test_telegram_required_env_vars(self):
        """Telegram declara TELEGRAM_TOKEN e TELEGRAM_CHAT_ID."""
        registry.load_builtin_providers()
        cls = registry.get("telegram")
        env_vars = cls.required_env_vars()
        assert "TELEGRAM_TOKEN" in env_vars
        assert "TELEGRAM_CHAT_ID" in env_vars

    def test_cli_required_env_vars_vazio(self):
        """CLI não precisa de variáveis de ambiente."""
        registry.load_builtin_providers()
        cls = registry.get("cli")
        assert cls.required_env_vars() == []

    def test_telegram_env_template(self):
        """Telegram gera template com placeholders."""
        registry.load_builtin_providers()
        cls = registry.get("telegram")
        template = cls.env_template()
        assert "TELEGRAM_TOKEN" in template
        assert "PREENCHA_AQUI" in template

    def test_cli_env_template_vazio(self):
        """CLI gera template vazio."""
        registry.load_builtin_providers()
        cls = registry.get("cli")
        assert cls.env_template() == ""
