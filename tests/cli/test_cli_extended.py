"""Testes estendidos para cobrir caminhos do CLI e daemon."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ai_squad.cli.main import (
    _build_image,
    _docker_compose_cmd,
    _find_source_dir,
    _get_container_status,
    _image_exists,
    cli,
)


@pytest.fixture
def runner():
    return CliRunner()


class TestHelperFunctions:
    """Testes para funções auxiliares do CLI."""

    def test_docker_compose_cmd(self, tmp_path):
        """Verifica montagem de comando docker compose."""
        cmd = _docker_compose_cmd(tmp_path, "up", "-d")
        assert cmd == [
            "docker",
            "compose",
            "-f",
            str(tmp_path / "docker-compose.yml"),
            "up",
            "-d",
        ]

    def test_image_exists_true(self):
        """Verifica detecção de imagem existente."""
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0)
            assert _image_exists() is True

    def test_image_exists_false(self):
        """Verifica detecção de imagem inexistente."""
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1)
            assert _image_exists() is False

    def test_get_container_status_running(self):
        """Verifica status running."""
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="running\n")
            assert _get_container_status("test") == "running"

    def test_get_container_status_stopped(self):
        """Verifica status stopped quando container não existe."""
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1)
            assert _get_container_status("test") == "stopped"

    def test_find_source_dir_cwd(self, tmp_path, monkeypatch):
        """Verifica busca de pyproject.toml no diretório atual."""
        (tmp_path / "pyproject.toml").touch()
        monkeypatch.chdir(tmp_path)
        assert _find_source_dir() == tmp_path

    def test_build_image_falha(self, tmp_path):
        """Verifica tratamento de erro no build."""
        with (
            patch("ai_squad.cli.main._find_source_dir", return_value=tmp_path),
            patch("ai_squad.cli.main._generate_wheel", return_value=True),
            patch("ai_squad.docker.get_docker_dir", return_value=tmp_path),
            patch("subprocess.run") as mock_run,
        ):
            (tmp_path / "Dockerfile").touch()
            mock_run.return_value = MagicMock(returncode=1)
            with pytest.raises(SystemExit):
                _build_image()


class TestCLIStartExtended:
    """Testes estendidos para o comando start."""

    def test_start_all_sem_times(self, runner, tmp_path):
        """Verifica start --all sem times."""
        with patch("ai_squad.cli.main._get_manager") as mock:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            mock.return_value = manager

            result = runner.invoke(cli, ["start", "--all"])

        assert "Nenhum time" in result.output

    def test_start_com_imagem_e_env_valido(self, runner, tmp_path):
        """Verifica start bem-sucedido."""
        repo = tmp_path / "repo"
        repo.mkdir()

        with (
            patch("ai_squad.cli.main._get_manager") as mock_mgr,
            patch("ai_squad.cli.main._image_exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            team_dir = manager.create("ok", str(repo))

            # Preenche .env (comuns + tokens do Telegram, que é o default)
            from ai_squad.cli.templates.config import COMMON_REQUIRED_ENV_VARS

            all_vars = list(COMMON_REQUIRED_ENV_VARS) + ["TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
            env = "\n".join(f"{v}=valor_real" for v in all_vars)
            (team_dir / ".env").write_text(env)

            mock_mgr.return_value = manager
            mock_run.return_value = MagicMock(returncode=0)

            result = runner.invoke(cli, ["start", "ok", "--docker"])

        assert "iniciado" in result.output.lower() or "Iniciando" in result.output

    def test_start_docker_compose_falha(self, runner, tmp_path):
        """Verifica tratamento de erro no docker-compose up."""
        repo = tmp_path / "repo"
        repo.mkdir()

        with (
            patch("ai_squad.cli.main._get_manager") as mock_mgr,
            patch("ai_squad.cli.main._image_exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            team_dir = manager.create("fail", str(repo))

            from ai_squad.cli.templates.config import COMMON_REQUIRED_ENV_VARS

            all_vars = list(COMMON_REQUIRED_ENV_VARS) + ["TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
            env = "\n".join(f"{v}=valor" for v in all_vars)
            (team_dir / ".env").write_text(env)

            mock_mgr.return_value = manager
            mock_run.return_value = MagicMock(returncode=1, stderr="connection refused")

            result = runner.invoke(cli, ["start", "fail", "--docker"])

        assert "Erro" in result.output or "erro" in result.output


class TestCLIStopExtended:
    """Testes estendidos para o comando stop."""

    def test_stop_all_com_times(self, runner, tmp_path):
        """Verifica stop --all com times existentes."""
        repo = tmp_path / "repo"
        repo.mkdir()

        with patch("ai_squad.cli.main._get_manager") as mock_mgr, patch("subprocess.run") as mock_run:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            manager.create("t1", str(repo))
            mock_mgr.return_value = manager
            mock_run.return_value = MagicMock(returncode=0)

            result = runner.invoke(cli, ["stop", "--all"])

        assert "Parando" in result.output

    def test_stop_docker_compose_falha(self, runner, tmp_path):
        """Verifica tratamento de erro no docker-compose down."""
        repo = tmp_path / "repo"
        repo.mkdir()

        with patch("ai_squad.cli.main._get_manager") as mock_mgr, patch("subprocess.run") as mock_run:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            manager.create("fail", str(repo))
            mock_mgr.return_value = manager
            mock_run.return_value = MagicMock(returncode=1, stderr="not running")

            result = runner.invoke(cli, ["stop", "fail"])

        assert "Erro" in result.output or "erro" in result.output


class TestCLIStatusExtended:
    """Testes estendidos para o comando status."""

    def test_status_com_demandas(self, runner, tmp_path):
        """Verifica exibição de demandas ativas."""
        repo = tmp_path / "repo"
        repo.mkdir()

        with (
            patch("ai_squad.cli.main._get_manager") as mock_mgr,
            patch("ai_squad.cli.main._get_container_status", return_value="running"),
        ):
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            team_dir = manager.create("active", str(repo))

            # Cria arquivo de estado
            state_dir = team_dir / "state"
            demand = {
                "demand_id": "demand-abc123",
                "state": "dev_working",
                "description": "Criar API de autenticação",
            }
            (state_dir / "demand-abc123.json").write_text(json.dumps(demand), encoding="utf-8")

            mock_mgr.return_value = manager
            result = runner.invoke(cli, ["status", "active"])

        assert "demand-abc123" in result.output
        assert "dev_working" in result.output


class TestCLILogs:
    """Testes para o comando logs."""

    def test_logs_time_inexistente(self, runner, tmp_path):
        """Verifica erro com time inexistente."""
        with patch("ai_squad.cli.main._get_manager") as mock:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            mock.return_value = manager

            result = runner.invoke(cli, ["logs", "inexistente"])

        assert result.exit_code != 0

    def test_logs_executa_docker_compose(self, runner, tmp_path):
        """Verifica que logs chama docker compose logs."""
        repo = tmp_path / "repo"
        repo.mkdir()

        with patch("ai_squad.cli.main._get_manager") as mock_mgr, patch("subprocess.run") as mock_run:
            from ai_squad.cli.team_manager import TeamManager

            manager = TeamManager(base_dir=tmp_path / ".ai-squad")
            manager.create("logtest", str(repo))
            mock_mgr.return_value = manager
            mock_run.return_value = MagicMock(returncode=0)

            result = runner.invoke(cli, ["logs", "logtest"])

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "logs" in cmd
        assert "-f" in cmd
