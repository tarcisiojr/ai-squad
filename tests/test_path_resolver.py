"""Testes para PathResolver."""

from pathlib import Path

import pytest

from src.path_resolver import PathResolver


class TestPathResolverLocal:
    """Testes para modo local."""

    def test_workspace_eh_base_dir(self, tmp_path):
        """Workspace no modo local é o base_dir."""
        resolver = PathResolver("local", tmp_path)
        assert resolver.workspace == tmp_path

    def test_agents_dir_dentro_de_ai_squad(self, tmp_path):
        """Agents dir fica em .ai-squad/agents."""
        resolver = PathResolver("local", tmp_path)
        assert resolver.agents_dir == tmp_path / ".ai-squad" / "agents"

    def test_state_dir_dentro_de_ai_squad(self, tmp_path):
        """State dir fica em .ai-squad/state."""
        resolver = PathResolver("local", tmp_path)
        assert resolver.state_dir == tmp_path / ".ai-squad" / "state"

    def test_config_path_dentro_de_ai_squad(self, tmp_path):
        """Config path fica em .ai-squad/config.yaml."""
        resolver = PathResolver("local", tmp_path)
        assert resolver.config_path == tmp_path / ".ai-squad" / "config.yaml"

    def test_pipeline_dir_dentro_de_ai_squad(self, tmp_path):
        """Pipeline dir fica em .ai-squad/pipeline."""
        resolver = PathResolver("local", tmp_path)
        assert resolver.pipeline_dir == tmp_path / ".ai-squad" / "pipeline"

    def test_env_path_dentro_de_ai_squad(self, tmp_path):
        """Env path fica em .ai-squad/.env."""
        resolver = PathResolver("local", tmp_path)
        assert resolver.env_path == tmp_path / ".ai-squad" / ".env"

    def test_global_skills_dir_no_home(self):
        """Skills globais ficam em ~/.ai-squad/skills."""
        resolver = PathResolver("local", Path("/tmp/projeto"))
        assert resolver.global_skills_dir == Path.home() / ".ai-squad" / "skills"


class TestPathResolverDocker:
    """Testes para modo docker."""

    def test_workspace_eh_workspace(self):
        """Workspace no docker é /workspace."""
        resolver = PathResolver("docker")
        assert resolver.workspace == Path("/workspace")

    def test_agents_dir_eh_app_agents(self):
        """Agents dir no docker é /app/agents."""
        resolver = PathResolver("docker")
        assert resolver.agents_dir == Path("/app/agents")

    def test_state_dir_eh_app_state(self):
        """State dir no docker é /app/state."""
        resolver = PathResolver("docker")
        assert resolver.state_dir == Path("/app/state")

    def test_config_path_eh_app_config(self):
        """Config path no docker é /app/config.yaml."""
        resolver = PathResolver("docker")
        assert resolver.config_path == Path("/app/config.yaml")

    def test_pipeline_dir_eh_app_pipeline(self):
        """Pipeline dir no docker é /app/pipeline."""
        resolver = PathResolver("docker")
        assert resolver.pipeline_dir == Path("/app/pipeline")

    def test_global_skills_dir_eh_app_global(self):
        """Skills globais no docker é /app/global-skills."""
        resolver = PathResolver("docker")
        assert resolver.global_skills_dir == Path("/app/global-skills")


class TestPathResolverValidacao:
    """Testes de validação."""

    def test_modo_invalido_levanta_erro(self):
        """Modo inválido levanta ValueError."""
        with pytest.raises(ValueError, match="Modo inválido"):
            PathResolver("invalido")

    def test_mode_exposto(self, tmp_path):
        """Atributo mode é acessível."""
        resolver = PathResolver("local", tmp_path)
        assert resolver.mode == "local"
