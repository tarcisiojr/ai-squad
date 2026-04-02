"""Testes para comandos CLI do ai-squad."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ai_squad.cli.main import cli


@pytest.fixture
def runner():
    """Cria CliRunner para testes."""
    return CliRunner()


@pytest.fixture
def mock_manager(tmp_path):
    """Cria TeamManager com diretório temporário."""
    from ai_squad.cli.team_manager import TeamManager

    manager = TeamManager(base_dir=tmp_path / ".ai-squad")
    return manager


class TestCLICreate:
    """Testes para o comando create."""

    def test_create_com_sucesso(self, runner, tmp_path):
        """Verifica criação de time via CLI."""
        repo = tmp_path / "repo"
        repo.mkdir()

        with patch("ai_squad.cli.main._get_manager") as mock:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            mock.return_value = manager

            result = runner.invoke(cli, ["create", "test-team", "--repo", str(repo)])

        assert result.exit_code == 0
        assert "test-team" in result.output
        assert "criado" in result.output

    def test_create_repo_inexistente(self, runner, tmp_path):
        """Verifica erro quando repo não existe."""
        with patch("ai_squad.cli.main._get_manager") as mock:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            mock.return_value = manager

            result = runner.invoke(cli, ["create", "test", "--repo", "/inexistente"])

        assert result.exit_code != 0
        assert "não encontrado" in result.output

    def test_create_time_duplicado(self, runner, tmp_path):
        """Verifica erro quando time já existe."""
        repo = tmp_path / "repo"
        repo.mkdir()

        with patch("ai_squad.cli.main._get_manager") as mock:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            mock.return_value = manager

            runner.invoke(cli, ["create", "dup", "--repo", str(repo)])
            result = runner.invoke(cli, ["create", "dup", "--repo", str(repo)])

        assert result.exit_code != 0
        assert "já existe" in result.output


class TestCLIList:
    """Testes para o comando list."""

    def test_list_sem_times(self, runner, tmp_path):
        """Verifica mensagem quando não há times."""
        with patch("ai_squad.cli.main._get_manager") as mock:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            mock.return_value = manager

            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "Nenhum time" in result.output

    def test_list_com_times(self, runner, tmp_path):
        """Verifica listagem de times existentes."""
        repo = tmp_path / "repo"
        repo.mkdir()

        with (
            patch("ai_squad.cli.main._get_manager") as mock,
            patch("ai_squad.cli.main._get_container_status", return_value="stopped"),
        ):
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            manager.create("time-a", str(repo))
            mock.return_value = manager

            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "time-a" in result.output


class TestCLIStart:
    """Testes para o comando start."""

    def test_start_sem_nome(self, runner):
        """Verifica erro quando nome não é fornecido."""
        result = runner.invoke(cli, ["start"])
        assert result.exit_code != 0

    def test_start_env_nao_preenchido(self, runner, tmp_path):
        """Verifica erro quando .env tem placeholders."""
        repo = tmp_path / "repo"
        repo.mkdir()

        with patch("ai_squad.cli.main._get_manager") as mock:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            manager.create("test", str(repo))
            mock.return_value = manager

            result = runner.invoke(cli, ["start", "test", "--docker"])

        assert result.exit_code == 0  # Não faz sys.exit, apenas mostra erro
        assert "não preenchidas" in result.output

    def test_start_time_inexistente(self, runner, tmp_path):
        """Verifica erro quando time não existe."""
        with patch("ai_squad.cli.main._get_manager") as mock:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            mock.return_value = manager

            result = runner.invoke(cli, ["start", "inexistente", "--docker"])

        assert "não encontrado" in result.output


class TestCLIStop:
    """Testes para o comando stop."""

    def test_stop_sem_nome(self, runner):
        """Verifica erro quando nome não é fornecido."""
        result = runner.invoke(cli, ["stop"])
        assert result.exit_code != 0

    def test_stop_time_inexistente(self, runner, tmp_path):
        """Verifica erro quando time não existe."""
        with patch("ai_squad.cli.main._get_manager") as mock:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            mock.return_value = manager

            result = runner.invoke(cli, ["stop", "inexistente"])

        assert "não encontrado" in result.output


class TestCLIStatus:
    """Testes para o comando status."""

    def test_status_time_inexistente(self, runner, tmp_path):
        """Verifica erro quando time não existe."""
        with patch("ai_squad.cli.main._get_manager") as mock:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            mock.return_value = manager

            result = runner.invoke(cli, ["status", "inexistente"])

        assert result.exit_code != 0

    def test_status_sem_demandas(self, runner, tmp_path):
        """Verifica status quando não há demandas."""
        repo = tmp_path / "repo"
        repo.mkdir()

        with (
            patch("ai_squad.cli.main._get_manager") as mock,
            patch("ai_squad.cli.main._get_container_status", return_value="stopped"),
        ):
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            manager.create("test", str(repo))
            mock.return_value = manager

            result = runner.invoke(cli, ["status", "test"])

        assert result.exit_code == 0
        assert "Nenhuma demanda" in result.output


class TestCLIBuild:
    """Testes para o comando build."""

    def test_build_chama_docker(self, runner, tmp_path):
        """Verifica que build executa docker build."""
        (tmp_path / "Dockerfile").write_text("FROM python:3.11-slim")

        with (
            patch("ai_squad.cli.main._find_source_dir", return_value=tmp_path),
            patch("ai_squad.cli.main._generate_wheel", return_value=True),
            patch("ai_squad.docker.get_docker_dir", return_value=tmp_path),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(cli, ["build"])

        assert result.exit_code == 0
        assert "construída" in result.output.lower() or "Construindo" in result.output


class TestCLIAgentManagement:
    """Testes para add-agent, remove-agent, list-agents."""

    def _create_team(self, tmp_path):
        from ai_squad.cli.team_manager import TeamManager

        repo = tmp_path / "repo"
        repo.mkdir()
        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        manager.create("meu-time", str(repo))
        return manager

    def test_add_agent(self, runner, tmp_path):
        """Verifica adição de agente."""
        manager = self._create_team(tmp_path)

        with patch("ai_squad.cli.main._get_manager", return_value=manager):
            result = runner.invoke(
                cli,
                [
                    "add-agent",
                    "meu-time",
                    "security",
                    "--name",
                    "Security Agent",
                    "--avatar",
                    "🔒",
                    "--command",
                    "/sec",
                ],
            )

        assert result.exit_code == 0
        assert "adicionado" in result.output

        # Verifica arquivos criados
        agent_dir = manager.get_path("meu-time") / "agents" / "security"
        assert agent_dir.exists()
        assert (agent_dir / "AGENTS.md").exists()
        assert (agent_dir / "CLAUDE.md").is_symlink()
        assert (agent_dir / "skills").is_dir()

        # Verifica config.yaml atualizado
        import yaml

        config = yaml.safe_load((manager.get_path("meu-time") / "config.yaml").read_text())
        assert "security" in config["agents"]
        assert config["agents"]["security"]["avatar"] == "🔒"

    def test_add_agent_ja_existe(self, runner, tmp_path):
        """Verifica erro ao adicionar agente existente."""
        manager = self._create_team(tmp_path)

        with patch("ai_squad.cli.main._get_manager", return_value=manager):
            result = runner.invoke(cli, ["add-agent", "meu-time", "po"])

        assert result.exit_code != 0
        assert "já existe" in result.output

    def test_add_agent_time_inexistente(self, runner, tmp_path):
        """Verifica erro com time inexistente."""
        from ai_squad.cli.team_manager import TeamManager

        manager = TeamManager(base_dir=tmp_path / ".ai-squad")

        with patch("ai_squad.cli.main._get_manager", return_value=manager):
            result = runner.invoke(cli, ["add-agent", "fake", "sec"])

        assert result.exit_code != 0

    def test_remove_agent(self, runner, tmp_path):
        """Verifica remoção de agente."""
        manager = self._create_team(tmp_path)

        with patch("ai_squad.cli.main._get_manager", return_value=manager):
            # Adiciona e depois remove
            runner.invoke(cli, ["add-agent", "meu-time", "security"])
            result = runner.invoke(cli, ["remove-agent", "meu-time", "security", "--yes"])

        assert result.exit_code == 0
        assert "removido" in result.output
        assert not (manager.get_path("meu-time") / "agents" / "security").exists()

    def test_remove_squad_lead_bloqueado(self, runner, tmp_path):
        """Verifica que não pode remover squad-lead."""
        manager = self._create_team(tmp_path)

        with patch("ai_squad.cli.main._get_manager", return_value=manager):
            result = runner.invoke(cli, ["remove-agent", "meu-time", "squad-lead", "--yes"])

        assert result.exit_code != 0
        assert "Squad Lead" in result.output

    def test_list_agents(self, runner, tmp_path):
        """Verifica listagem de agentes."""
        manager = self._create_team(tmp_path)

        with patch("ai_squad.cli.main._get_manager", return_value=manager):
            result = runner.invoke(cli, ["list-agents", "meu-time"])

        assert result.exit_code == 0
        assert "Squad Lead" in result.output
        assert "po" in result.output.lower()
        assert "dev" in result.output.lower()
        assert "qa" in result.output.lower()


class TestCLIVersion:
    """Testes para a flag --version."""

    def test_version(self, runner):
        """Verifica exibição da versão."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "ai-squad" in result.output
