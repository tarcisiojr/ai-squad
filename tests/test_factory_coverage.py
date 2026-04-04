"""Testes adicionais para cobertura do factory.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from ai_squad.factory import (
    AgentConfig,
    HeartbeatConfig,
    KnowledgeConfig,
    PlatformConfig,
    PlatformFactory,
    SquadLeadConfig,
    SubmoduleConfig,
    ThreadTrackingConfig,
)


class TestPlatformConfigFromYaml:
    """Testes para PlatformConfig.from_yaml."""

    def test_config_com_activation_mode_invalido(self, tmp_path):
        """activation_mode inválido lança ValueError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-agent-sdk",
                    "messaging_provider": "telegram",
                    "activation_mode": "invalido",
                }
            )
        )
        with pytest.raises(ValueError, match="activation_mode"):
            PlatformConfig.from_yaml(config_file)

    def test_config_sem_messaging_provider(self, tmp_path):
        """Faltando messaging_provider lança ValueError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"ai_provider": "claude-agent-sdk"}))
        with pytest.raises(ValueError, match="messaging_provider"):
            PlatformConfig.from_yaml(config_file)

    def test_config_com_submodules_string(self, tmp_path):
        """Submodules como lista de strings são parseados."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-agent-sdk",
                    "messaging_provider": "telegram",
                    "agents": {
                        "dev": {
                            "name": "Dev",
                            "avatar": "⚙️",
                            "submodules": ["backend/", "api/"],
                        }
                    },
                }
            )
        )
        config = PlatformConfig.from_yaml(config_file)
        assert len(config.agents["dev"].submodules) == 2
        assert config.agents["dev"].submodules[0].path == "backend/"

    def test_config_com_submodules_dict(self, tmp_path):
        """Submodules como lista de dicts são parseados."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-agent-sdk",
                    "messaging_provider": "telegram",
                    "agents": {
                        "dev": {
                            "name": "Dev",
                            "avatar": "⚙️",
                            "submodules": [
                                {"path": "backend/", "description": "Backend API"},
                            ],
                        }
                    },
                }
            )
        )
        config = PlatformConfig.from_yaml(config_file)
        sub = config.agents["dev"].submodules[0]
        assert sub.path == "backend/"
        assert sub.description == "Backend API"

    def test_config_com_thread_tracking(self, tmp_path):
        """Thread tracking é parseado corretamente."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-agent-sdk",
                    "messaging_provider": "telegram",
                    "thread_tracking": {
                        "standby_timeout": 600,
                        "inactive_thread_ttl": 3600,
                        "handoff_message": False,
                    },
                }
            )
        )
        config = PlatformConfig.from_yaml(config_file)
        assert config.thread_tracking.standby_timeout == 600
        assert config.thread_tracking.handoff_message is False

    def test_config_com_knowledge(self, tmp_path):
        """Knowledge config é parseada corretamente."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-agent-sdk",
                    "messaging_provider": "telegram",
                    "knowledge": {
                        "enabled": True,
                        "use_qmd": True,
                        "knowledge_dir": "/custom/kb",
                    },
                }
            )
        )
        config = PlatformConfig.from_yaml(config_file)
        assert config.knowledge.enabled is True
        assert config.knowledge.use_qmd is True
        assert config.knowledge.knowledge_dir == "/custom/kb"

    def test_config_com_heartbeat(self, tmp_path):
        """Heartbeat config é parseada corretamente."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-agent-sdk",
                    "messaging_provider": "telegram",
                    "heartbeat": {
                        "enabled": False,
                        "interval": 60,
                        "stall_timeout": 120,
                    },
                }
            )
        )
        config = PlatformConfig.from_yaml(config_file)
        assert config.heartbeat.enabled is False
        assert config.heartbeat.interval == 60


class TestValidateRequiredTokens:
    """Testes para validate_required_tokens."""

    def test_copilot_sem_token(self, monkeypatch):
        """Copilot não requer token."""
        config = PlatformConfig(
            ai_provider="copilot",
            messaging_provider="cli",
        )
        missing = config.validate_required_tokens()
        # Copilot não tem tokens obrigatórios de IA (auth via CLI)
        assert not any("COPILOT" in m for m in missing)

    def test_agno_requer_google_api_key(self, monkeypatch):
        """Agno requer GOOGLE_API_KEY."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        config = PlatformConfig(
            ai_provider="agno",
            messaging_provider="cli",
        )
        missing = config.validate_required_tokens()
        assert "GOOGLE_API_KEY" in missing


class TestPlatformFactoryRegistration:
    """Testes para registro no PlatformFactory."""

    def test_registra_e_cria_message_bus(self):
        """Registra e cria MessageBus via factory."""
        factory = PlatformFactory()
        mock_cls = MagicMock()
        factory.register_message_bus("mock", mock_cls)

        config = PlatformConfig(
            ai_provider="test",
            messaging_provider="mock",
        )
        factory.create_message_bus(config)
        mock_cls.assert_called_once()

    def test_message_bus_nao_registrado_falha(self):
        """Erro ao criar MessageBus não registrado."""
        factory = PlatformFactory()
        config = PlatformConfig(
            ai_provider="test",
            messaging_provider="nao-existe",
        )
        with pytest.raises(ValueError, match="não registrado"):
            factory.create_message_bus(config)

    def test_registra_e_cria_ai_adapter(self):
        """Registra e cria AIAdapter via factory."""
        factory = PlatformFactory()
        mock_cls = MagicMock()
        factory.register_ai_adapter("mock-ai", mock_cls)

        config = PlatformConfig(
            ai_provider="mock-ai",
            messaging_provider="test",
        )
        factory.create_ai_adapter(config)
        mock_cls.assert_called_once()

    def test_ai_adapter_nao_registrado_falha(self):
        """Erro ao criar AIAdapter não registrado."""
        factory = PlatformFactory()
        config = PlatformConfig(
            ai_provider="nao-existe",
            messaging_provider="test",
        )
        with pytest.raises(ValueError, match="não registrado"):
            factory.create_ai_adapter(config)

    def test_ai_adapter_com_model(self):
        """AI model da config é passado ao adapter."""
        factory = PlatformFactory()
        mock_cls = MagicMock()
        factory.register_ai_adapter("mock-ai", mock_cls)

        config = PlatformConfig(
            ai_provider="mock-ai",
            messaging_provider="test",
            ai_model="claude-sonnet",
        )
        factory.create_ai_adapter(config)
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet"
