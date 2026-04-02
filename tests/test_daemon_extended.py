"""Testes estendidos para o daemon — cobertura de caminhos adicionais."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
import yaml

from ai_squad.daemon import Daemon
from ai_squad.path_resolver import PathResolver


def _local_daemon(base_dir: Path) -> Daemon:
    """Cria Daemon com PathResolver local apontando para base_dir."""
    paths = PathResolver("local", base_dir)
    (base_dir / ".ai-squad").mkdir(exist_ok=True)
    return Daemon(path_resolver=paths)


def _write_config(base_dir: Path, data: dict) -> None:
    """Escreve config.yaml no diretório .ai-squad/."""
    config_dir = base_dir / ".ai-squad"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.yaml").write_text(yaml.dump(data))


class TestDaemonConfig:
    """Testes para carregamento de config no daemon."""

    def test_load_config_com_yaml(self, tmp_path, monkeypatch):
        """Verifica carregamento de config com arquivo YAML."""
        for var in ["AI_PROVIDER", "MESSAGING_PROVIDER", "AGENT_TIMEOUT", "STATE_DIR", "REPO_PATH"]:
            monkeypatch.delenv(var, raising=False)

        _write_config(
            tmp_path,
            {
                "ai_provider": "claude-code",
                "messaging_provider": "telegram",
                "agent_timeout": 600,
                "repo_path": str(tmp_path),
            },
        )

        daemon = _local_daemon(tmp_path)
        config = daemon._load_config()

        assert config.ai_provider == "claude-code"
        assert config.agent_timeout == 600

    def test_load_config_env_override_yaml(self, tmp_path, monkeypatch):
        """Verifica que env vars sobrescrevem YAML."""
        monkeypatch.setenv("AI_PROVIDER", "custom-provider")
        monkeypatch.setenv("AGENT_TIMEOUT", "999")

        _write_config(
            tmp_path,
            {
                "ai_provider": "claude-code",
                "messaging_provider": "telegram",
                "agent_timeout": 300,
            },
        )

        daemon = _local_daemon(tmp_path)
        config = daemon._load_config()

        assert config.ai_provider == "custom-provider"
        assert config.agent_timeout == 999

    def test_load_config_com_dotenv(self, tmp_path, monkeypatch):
        """Verifica que load_dotenv é chamado quando .env existe."""
        for var in ["AI_PROVIDER", "MESSAGING_PROVIDER", "AGENT_TIMEOUT", "STATE_DIR", "REPO_PATH"]:
            monkeypatch.delenv(var, raising=False)

        env_file = tmp_path / ".ai-squad" / ".env"
        (tmp_path / ".ai-squad").mkdir(exist_ok=True)
        env_file.write_text("AGENT_TIMEOUT=777\n")

        _write_config(
            tmp_path,
            {
                "ai_provider": "claude-code",
                "messaging_provider": "cli",
                "agent_timeout": 300,
            },
        )

        monkeypatch.setenv("AGENT_TIMEOUT", "777")

        daemon = _local_daemon(tmp_path)
        with patch("ai_squad.daemon.load_dotenv"):
            config = daemon._load_config()

        assert config.agent_timeout == 777


class TestDaemonSetup:
    """Testes para setup de componentes."""

    def test_setup_components(self, tmp_path, monkeypatch):
        """Verifica inicialização de componentes."""
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-test")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        monkeypatch.setenv("TELEGRAM_TOKEN", "bot-test")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        _write_config(
            tmp_path,
            {
                "ai_provider": "claude-code",
                "messaging_provider": "telegram",
            },
        )

        (tmp_path / ".ai-squad" / "state").mkdir(parents=True, exist_ok=True)

        daemon = _local_daemon(tmp_path)
        daemon._setup_components()

        assert daemon._engine is not None
        assert daemon._bus is not None
        assert daemon._config is not None


class TestDaemonNonBlocking:
    """Testes para processamento nao-bloqueante."""

    @pytest.mark.asyncio
    async def test_mensagem_processa_imediatamente(self, monkeypatch):
        """Verifica que mensagens sao processadas inline, sem fila."""
        daemon = Daemon()
        bus = AsyncMock()
        type(bus).default_chat_id = PropertyMock(return_value="12345")
        type(bus).supports_threads = PropertyMock(return_value=False)
        daemon._bus = bus
        daemon._engine = AsyncMock()
        daemon._config = MagicMock()
        daemon._config.agents = {}

        await daemon._handle_new_demand("Criar site")

        # Squad Lead chamado diretamente (sem fila)
        daemon._engine.run_squad_lead.assert_called_once()

    @pytest.mark.asyncio
    async def test_erro_nao_derruba_daemon(self, monkeypatch):
        """Verifica que erro no processamento nao derruba o daemon."""
        daemon = Daemon()
        bus = AsyncMock()
        type(bus).default_chat_id = PropertyMock(return_value="12345")
        type(bus).supports_threads = PropertyMock(return_value=False)
        daemon._bus = bus
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

        health = Path("/tmp/ai-squad-healthy")
        assert health.exists()

        daemon._remove_healthcheck()
        assert not health.exists()

    @pytest.mark.asyncio
    async def test_healthcheck_loop_respeita_shutdown(self):
        """Verifica que healthcheck para no shutdown."""
        daemon = Daemon()
        daemon._shutdown_event.set()

        await daemon._healthcheck_loop()
