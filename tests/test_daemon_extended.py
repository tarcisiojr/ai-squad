"""Testes estendidos para o daemon — cobertura de caminhos adicionais."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from src.daemon import Daemon


class TestDaemonConfig:
    """Testes para carregamento de config no daemon."""

    def test_load_config_com_yaml(self, tmp_path, monkeypatch):
        """Verifica carregamento de config com arquivo YAML."""
        monkeypatch.chdir(tmp_path)
        for var in ["AI_PROVIDER", "MESSAGING_PROVIDER", "AGENT_TIMEOUT", "STATE_DIR", "REPO_PATH"]:
            monkeypatch.delenv(var, raising=False)

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({
                "ai_provider": "claude-code",
                "messaging_provider": "telegram",
                "agent_timeout": 600,
                "repo_path": str(tmp_path),
            })
        )

        daemon = Daemon()
        config = daemon._load_config()

        assert config.ai_provider == "claude-code"
        assert config.agent_timeout == 600

    def test_load_config_env_override_yaml(self, tmp_path, monkeypatch):
        """Verifica que env vars sobrescrevem YAML."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AI_PROVIDER", "custom-provider")
        monkeypatch.setenv("AGENT_TIMEOUT", "999")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({
                "ai_provider": "claude-code",
                "messaging_provider": "telegram",
                "agent_timeout": 300,
            })
        )

        daemon = Daemon()
        config = daemon._load_config()

        assert config.ai_provider == "custom-provider"
        assert config.agent_timeout == 999

    def test_load_config_com_dotenv(self, tmp_path, monkeypatch):
        """Verifica que load_dotenv é chamado quando .env existe."""
        monkeypatch.chdir(tmp_path)
        for var in ["AI_PROVIDER", "MESSAGING_PROVIDER", "AGENT_TIMEOUT", "STATE_DIR", "REPO_PATH"]:
            monkeypatch.delenv(var, raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text("AGENT_TIMEOUT=777\n")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({
                "ai_provider": "claude-code",
                "messaging_provider": "cli",
                "agent_timeout": 300,
            })
        )

        monkeypatch.setenv("AGENT_TIMEOUT", "777")

        daemon = Daemon()
        with patch("src.daemon.load_dotenv"):
            config = daemon._load_config()

        assert config.agent_timeout == 777


class TestDaemonSetup:
    """Testes para setup de componentes."""

    def test_setup_components(self, tmp_path, monkeypatch):
        """Verifica inicialização de componentes."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-test")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        monkeypatch.setenv("TELEGRAM_TOKEN", "bot-test")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump({
                "ai_provider": "claude-code",
                "messaging_provider": "telegram",
            })
        )

        (tmp_path / "state").mkdir()

        daemon = Daemon()
        daemon._setup_components()

        assert daemon._engine is not None
        assert daemon._bus is not None
        assert daemon._config is not None


class TestDaemonNonBlocking:
    """Testes para processamento nao-bloqueante."""

    @pytest.mark.asyncio
    async def test_mensagem_processa_imediatamente(self, monkeypatch):
        """Verifica que mensagens sao processadas inline, sem fila."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._bus = AsyncMock()
        daemon._engine = AsyncMock()
        daemon._config = MagicMock()
        daemon._config.agents = {}

        await daemon._handle_new_demand("Criar site")

        # Squad Lead chamado diretamente (sem fila)
        daemon._engine.run_squad_lead.assert_called_once()

    @pytest.mark.asyncio
    async def test_erro_nao_derruba_daemon(self, monkeypatch):
        """Verifica que erro no processamento nao derruba o daemon."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._bus = AsyncMock()
        daemon._engine = AsyncMock()
        daemon._engine.run_squad_lead.side_effect = RuntimeError("Falha!")
        daemon._config = MagicMock()
        daemon._config.agents = {}

        # Nao deve lancar excecao
        await daemon._handle_new_demand("Demanda que falha")

        daemon._bus.notify.assert_called()


class TestDaemonHealthcheck:
    """Testes para healthcheck."""

    def test_write_and_remove_healthcheck(self):
        """Verifica criação e remoção do arquivo de health."""
        daemon = Daemon()
        daemon._write_healthcheck()

        health = Path("/tmp/ai-dev-team-healthy")
        assert health.exists()

        daemon._remove_healthcheck()
        assert not health.exists()

    @pytest.mark.asyncio
    async def test_healthcheck_loop_respeita_shutdown(self):
        """Verifica que healthcheck para no shutdown."""
        daemon = Daemon()
        daemon._shutdown_event.set()

        await daemon._healthcheck_loop()
