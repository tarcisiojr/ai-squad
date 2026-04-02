"""Testes para PlatformConfig com variáveis de ambiente e validação."""

import os

import yaml

from ai_squad.factory import PlatformConfig


class TestPlatformConfigEnvOverrides:
    """Testes para override de config via variáveis de ambiente."""

    def test_env_override_ai_provider(self, tmp_path, monkeypatch):
        """Verifica que AI_PROVIDER sobrescreve valor do YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "original",
                    "messaging_provider": "cli",
                }
            )
        )
        monkeypatch.setenv("AI_PROVIDER", "claude-code-override")

        config = PlatformConfig.from_yaml(config_file)
        assert config.ai_provider == "claude-code-override"

    def test_env_override_agent_timeout(self, tmp_path, monkeypatch):
        """Verifica que AGENT_TIMEOUT sobrescreve valor do YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-code",
                    "messaging_provider": "cli",
                    "agent_timeout": 300,
                }
            )
        )
        monkeypatch.setenv("AGENT_TIMEOUT", "600")

        config = PlatformConfig.from_yaml(config_file)
        assert config.agent_timeout == 600

    def test_env_sem_override_mantem_yaml(self, tmp_path, monkeypatch):
        """Verifica que sem env vars o YAML prevalece."""
        # Limpa env vars que poderiam interferir
        for var in ["AI_PROVIDER", "MESSAGING_PROVIDER", "AGENT_TIMEOUT", "STATE_DIR", "REPO_PATH"]:
            monkeypatch.delenv(var, raising=False)

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-code",
                    "messaging_provider": "telegram",
                    "agent_timeout": 500,
                }
            )
        )

        config = PlatformConfig.from_yaml(config_file)
        assert config.ai_provider == "claude-code"
        assert config.agent_timeout == 500


class TestPlatformConfigRepoPath:
    """Testes para campo repo_path."""

    def test_repo_path_do_yaml(self, tmp_path, monkeypatch):
        """Verifica que repo_path é carregado do YAML."""
        for var in ["AI_PROVIDER", "MESSAGING_PROVIDER", "AGENT_TIMEOUT", "STATE_DIR", "REPO_PATH"]:
            monkeypatch.delenv(var, raising=False)

        repo = tmp_path / "meu-repo"
        repo.mkdir()

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-code",
                    "messaging_provider": "cli",
                    "repo_path": str(repo),
                }
            )
        )

        config = PlatformConfig.from_yaml(config_file)
        assert config.repo_path == str(repo)

    def test_repo_path_resolvido_absoluto(self, tmp_path, monkeypatch):
        """Verifica que repo_path é resolvido para caminho absoluto."""
        for var in ["AI_PROVIDER", "MESSAGING_PROVIDER", "AGENT_TIMEOUT", "STATE_DIR", "REPO_PATH"]:
            monkeypatch.delenv(var, raising=False)

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-code",
                    "messaging_provider": "cli",
                    "repo_path": str(tmp_path),
                }
            )
        )

        config = PlatformConfig.from_yaml(config_file)
        # Deve ser caminho absoluto
        assert os.path.isabs(config.repo_path)

    def test_repo_path_via_env(self, tmp_path, monkeypatch):
        """Verifica override de repo_path via REPO_PATH env var."""
        monkeypatch.setenv("REPO_PATH", "/novo/caminho")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-code",
                    "messaging_provider": "cli",
                    "repo_path": "/original",
                }
            )
        )

        config = PlatformConfig.from_yaml(config_file)
        assert "/novo/caminho" in config.repo_path


class TestPlatformConfigValidation:
    """Testes para validação de tokens obrigatórios."""

    def test_validate_tokens_ausentes(self, monkeypatch):
        """Verifica detecção de tokens ausentes."""
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

        config = PlatformConfig(
            ai_provider="claude-code",
            messaging_provider="telegram",
        )

        missing = config.validate_required_tokens()
        assert "CLAUDE_CODE_OAUTH_TOKEN" in missing
        # GITHUB_TOKEN agora é opcional
        assert "TELEGRAM_TOKEN" in missing
        assert "TELEGRAM_CHAT_ID" in missing

    def test_validate_tokens_com_placeholder(self, monkeypatch):
        """Verifica que placeholders são detectados como ausentes."""
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "PREENCHA_AQUI_token")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_real")
        monkeypatch.setenv("TELEGRAM_TOKEN", "bot_real")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        config = PlatformConfig(
            ai_provider="claude-code",
            messaging_provider="telegram",
        )

        missing = config.validate_required_tokens()
        assert "CLAUDE_CODE_OAUTH_TOKEN" in missing
        assert "GITHUB_TOKEN" not in missing

    def test_validate_tokens_todos_preenchidos(self, monkeypatch):
        """Verifica que tokens válidos passam na validação."""
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-real")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_real")
        monkeypatch.setenv("TELEGRAM_TOKEN", "bot_real")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        config = PlatformConfig(
            ai_provider="claude-code",
            messaging_provider="telegram",
        )

        missing = config.validate_required_tokens()
        assert missing == []
