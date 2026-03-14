"""Testes para configuração e factory de providers."""

import os
import tempfile

import pytest
import yaml

from src.factory import PlatformConfig, PlatformFactory, PersonaConfig
from src.barramento.interface import MessageBus
from src.adapters.interface import AIAgentAdapter
from src.models import AgentStatus


# Implementação fake para testes
class FakeMessageBus(MessageBus):
    """Implementação fake de MessageBus para testes."""

    async def send_message(self, user_id: str, text: str) -> None:
        pass

    async def send_approval_request(
        self, user_id: str, question: str, options: list[str]
    ) -> str:
        return options[0]

    async def receive_message(self, callback) -> None:
        pass

    async def receive_voice(self, callback) -> None:
        pass

    async def notify(self, user_id: str, text: str) -> None:
        pass


class FakeAIAdapter(AIAgentAdapter):
    """Implementação fake de AIAgentAdapter para testes."""

    async def run(self, prompt: str, context: dict) -> str:
        return "resultado fake"

    async def ask(self, question: str) -> str:
        return "resposta fake"

    def status(self) -> AgentStatus:
        return AgentStatus.IDLE

    def on_human_needed(self, callback) -> None:
        pass


class TestPlatformConfig:
    """Testes para carregamento de configuração."""

    def test_carregamento_valido(self, tmp_path):
        """Verifica carregamento de YAML válido."""
        config_file = tmp_path / "platform.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-code",
                    "messaging_provider": "telegram",
                    "agent_timeout": 600,
                    "personas": {
                        "po": {"name": "PO Agent", "avatar": "📋"},
                    },
                }
            )
        )

        config = PlatformConfig.from_yaml(config_file)
        assert config.ai_provider == "claude-code"
        assert config.messaging_provider == "telegram"
        assert config.agent_timeout == 600
        assert "po" in config.personas
        assert config.personas["po"].name == "PO Agent"

    def test_valores_padrao(self, tmp_path):
        """Verifica que valores padrão são aplicados."""
        config_file = tmp_path / "platform.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-code",
                    "messaging_provider": "cli",
                }
            )
        )

        config = PlatformConfig.from_yaml(config_file)
        assert config.agent_timeout == 300
        assert config.state_dir == "state/"
        assert config.personas == {}

    def test_arquivo_nao_encontrado(self):
        """Verifica erro quando arquivo não existe."""
        with pytest.raises(FileNotFoundError):
            PlatformConfig.from_yaml("/caminho/inexistente.yaml")

    def test_ai_provider_obrigatorio(self, tmp_path):
        """Verifica erro quando ai_provider está ausente."""
        config_file = tmp_path / "platform.yaml"
        config_file.write_text(yaml.dump({"messaging_provider": "cli"}))

        with pytest.raises(ValueError, match="ai_provider"):
            PlatformConfig.from_yaml(config_file)

    def test_messaging_provider_obrigatorio(self, tmp_path):
        """Verifica erro quando messaging_provider está ausente."""
        config_file = tmp_path / "platform.yaml"
        config_file.write_text(yaml.dump({"ai_provider": "claude-code"}))

        with pytest.raises(ValueError, match="messaging_provider"):
            PlatformConfig.from_yaml(config_file)

    def test_yaml_invalido(self, tmp_path):
        """Verifica erro quando YAML contém formato inválido."""
        config_file = tmp_path / "platform.yaml"
        config_file.write_text("apenas uma string")

        with pytest.raises(ValueError, match="formato YAML"):
            PlatformConfig.from_yaml(config_file)


class TestPlatformFactory:
    """Testes para factory de providers."""

    def setup_method(self):
        """Configura factory para cada teste."""
        self.factory = PlatformFactory()
        self.config = PlatformConfig(
            ai_provider="claude-code",
            messaging_provider="cli",
        )

    def test_registrar_e_criar_message_bus(self):
        """Verifica registro e criação de MessageBus."""
        self.factory.register_message_bus("cli", FakeMessageBus)
        bus = self.factory.create_message_bus(self.config)
        assert isinstance(bus, MessageBus)

    def test_registrar_e_criar_ai_adapter(self):
        """Verifica registro e criação de AIAgentAdapter."""
        self.factory.register_ai_adapter("claude-code", FakeAIAdapter)
        adapter = self.factory.create_ai_adapter(self.config)
        assert isinstance(adapter, AIAgentAdapter)

    def test_provider_mensageria_nao_registrado(self):
        """Verifica erro quando provider de mensageria não está registrado."""
        with pytest.raises(ValueError, match="não registrado"):
            self.factory.create_message_bus(self.config)

    def test_provider_ia_nao_registrado(self):
        """Verifica erro quando provider de IA não está registrado."""
        with pytest.raises(ValueError, match="não registrado"):
            self.factory.create_ai_adapter(self.config)

    def test_troca_de_provider(self):
        """Verifica que trocar provider na config muda a implementação."""
        self.factory.register_message_bus("cli", FakeMessageBus)
        self.factory.register_message_bus("telegram", FakeMessageBus)

        config_cli = PlatformConfig(
            ai_provider="claude-code", messaging_provider="cli"
        )
        config_telegram = PlatformConfig(
            ai_provider="claude-code", messaging_provider="telegram"
        )

        bus_cli = self.factory.create_message_bus(config_cli)
        bus_telegram = self.factory.create_message_bus(config_telegram)

        assert isinstance(bus_cli, MessageBus)
        assert isinstance(bus_telegram, MessageBus)
