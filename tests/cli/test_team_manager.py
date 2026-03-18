"""Testes para o gerenciador de times."""

import pytest
import yaml

from src.cli.team_manager import (
    TeamExistsError,
    TeamManager,
    TeamNotFoundError,
)
from src.cli.templates.config import PLACEHOLDER_PREFIX, REQUIRED_ENV_VARS


class TestTeamManager:
    """Testes para TeamManager."""

    def test_create_time_com_sucesso(self, tmp_path):
        """Verifica criação completa de um novo time."""
        repo = tmp_path / "meu-repo"
        repo.mkdir()

        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        team_dir = manager.create("backend", str(repo))

        assert team_dir.exists()
        assert (team_dir / "config.yaml").exists()
        assert (team_dir / ".env").exists()
        assert (team_dir / "docker-compose.yml").exists()
        assert (team_dir / "state").is_dir()

    def test_create_gera_config_yaml_correto(self, tmp_path):
        """Verifica que config.yaml contém valores corretos."""
        repo = tmp_path / "meu-repo"
        repo.mkdir()

        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        team_dir = manager.create("api", str(repo))

        with open(team_dir / "config.yaml", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert config["ai_provider"] == "claude-agent-sdk"
        assert config["messaging_provider"] == "telegram"
        assert config["agent_timeout"] == 300
        assert config["repo_path"] == str(repo)
        assert "po" in config["agents"]
        assert "dev-backend" in config["agents"]
        assert "dev-frontend" in config["agents"]
        assert "code-review" in config["agents"]
        assert "qa" in config["agents"]

    def test_create_gera_env_com_placeholders(self, tmp_path):
        """Verifica que .env contém placeholders identificáveis."""
        repo = tmp_path / "repo"
        repo.mkdir()

        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        team_dir = manager.create("test", str(repo))

        env_content = (team_dir / ".env").read_text(encoding="utf-8")
        for var in REQUIRED_ENV_VARS:
            assert var in env_content
        assert PLACEHOLDER_PREFIX in env_content

    def test_create_gera_docker_compose_correto(self, tmp_path):
        """Verifica que docker-compose.yml contém nome e volumes corretos."""
        repo = tmp_path / "repo"
        repo.mkdir()

        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        team_dir = manager.create("web", str(repo))

        compose_content = (team_dir / "docker-compose.yml").read_text(encoding="utf-8")
        assert "adt-web" in compose_content
        assert str(repo) in compose_content
        assert "docker.sock" in compose_content
        assert "unless-stopped" in compose_content

    def test_create_time_ja_existe(self, tmp_path):
        """Verifica erro quando time já existe."""
        repo = tmp_path / "repo"
        repo.mkdir()

        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        manager.create("existente", str(repo))

        with pytest.raises(TeamExistsError, match="já existe"):
            manager.create("existente", str(repo))

    def test_create_repo_nao_existe(self, tmp_path):
        """Verifica erro quando diretório do repo não existe."""
        manager = TeamManager(base_dir=tmp_path / ".ai-squad")

        with pytest.raises(FileNotFoundError, match="não encontrado"):
            manager.create("test", "/caminho/inexistente")

    def test_exists_retorna_true_para_time_existente(self, tmp_path):
        """Verifica que exists retorna True para time existente."""
        repo = tmp_path / "repo"
        repo.mkdir()

        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        manager.create("meu-time", str(repo))

        assert manager.exists("meu-time") is True

    def test_exists_retorna_false_para_time_inexistente(self, tmp_path):
        """Verifica que exists retorna False para time inexistente."""
        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        assert manager.exists("inexistente") is False

    def test_list_teams_vazio(self, tmp_path):
        """Verifica lista vazia quando não há times."""
        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        assert manager.list_teams() == []

    def test_list_teams_com_times(self, tmp_path):
        """Verifica listagem de múltiplos times."""
        repo1 = tmp_path / "repo1"
        repo2 = tmp_path / "repo2"
        repo1.mkdir()
        repo2.mkdir()

        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        manager.create("alpha", str(repo1))
        manager.create("beta", str(repo2))

        teams = manager.list_teams()
        assert len(teams) == 2
        names = [t["name"] for t in teams]
        assert "alpha" in names
        assert "beta" in names

    def test_validate_env_com_placeholders(self, tmp_path):
        """Verifica que validate_env detecta placeholders."""
        repo = tmp_path / "repo"
        repo.mkdir()

        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        manager.create("test", str(repo))

        missing = manager.validate_env("test")
        assert set(missing) == set(REQUIRED_ENV_VARS)

    def test_validate_env_preenchido(self, tmp_path):
        """Verifica que validate_env aceita .env preenchido."""
        repo = tmp_path / "repo"
        repo.mkdir()

        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        team_dir = manager.create("test", str(repo))

        # Sobrescreve .env com valores reais
        env_content = "\n".join(
            f"{var}=valor_real_{var}" for var in REQUIRED_ENV_VARS
        )
        (team_dir / ".env").write_text(env_content, encoding="utf-8")

        missing = manager.validate_env("test")
        assert missing == []

    def test_validate_env_time_inexistente(self, tmp_path):
        """Verifica erro ao validar .env de time inexistente."""
        manager = TeamManager(base_dir=tmp_path / ".ai-squad")

        with pytest.raises(TeamNotFoundError):
            manager.validate_env("inexistente")

    def test_remove_time(self, tmp_path):
        """Verifica remoção de um time."""
        repo = tmp_path / "repo"
        repo.mkdir()

        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        manager.create("removivel", str(repo))
        assert manager.exists("removivel")

        manager.remove("removivel")
        assert not manager.exists("removivel")

    def test_remove_time_inexistente(self, tmp_path):
        """Verifica erro ao remover time inexistente."""
        manager = TeamManager(base_dir=tmp_path / ".ai-squad")

        with pytest.raises(TeamNotFoundError):
            manager.remove("inexistente")

    def test_get_path(self, tmp_path):
        """Verifica que get_path retorna caminho correto."""
        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        path = manager.get_path("meu-time")
        assert path == tmp_path / ".ai-squad" / "teams" / "meu-time"
