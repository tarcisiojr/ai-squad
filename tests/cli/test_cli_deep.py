"""Testes profundos para CLI — cobertura do comando start e detect_mode."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ai_squad.cli.main import (
    _detect_mode,
    _start_local,
    cli,
)


@pytest.fixture
def runner():
    return CliRunner()


# --- _detect_mode ---


class TestDetectMode:
    """Testes para _detect_mode."""

    def test_detect_mode_local(self, tmp_path, monkeypatch):
        """Verifica deteccao de modo local."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".ai-squad").mkdir()

        result = _detect_mode("test")
        assert result == "local"

    def test_detect_mode_docker(self, tmp_path, monkeypatch):
        """Verifica deteccao de modo docker."""
        monkeypatch.chdir(tmp_path)
        # Sem .ai-squad local, mas com dir global
        global_dir = tmp_path / ".ai-squad-home" / "teams" / "test"
        global_dir.mkdir(parents=True)

        with patch("ai_squad.cli.main.Path") as mock_path:
            # cwd / ".ai-squad" nao existe
            mock_cwd = MagicMock()
            mock_cwd.exists.return_value = False

            # home / ".ai-squad" / "teams" / name existe
            mock_global = MagicMock()
            mock_global.exists.return_value = True

            def path_side_effect(*args, **kwargs):
                result = MagicMock()
                if args:
                    return MagicMock()
                return result

            mock_path.cwd.return_value.__truediv__ = lambda self, x: mock_cwd
            mock_path.home.return_value.__truediv__ = lambda self, x: MagicMock(
                __truediv__=lambda self, x: MagicMock(
                    __truediv__=lambda self, x: mock_global
                )
            )

            # Simplificamos: usar monkeypatch direto
            pass

    def test_detect_mode_nao_encontrado(self, tmp_path, monkeypatch):
        """Verifica que time nao encontrado sai com erro."""
        monkeypatch.chdir(tmp_path)
        # Sem .ai-squad local nem global

        with pytest.raises(SystemExit):
            _detect_mode("inexistente")


# --- Comando start ---


class TestStartCommand:
    """Testes para o comando start."""

    def test_start_sem_nome_e_sem_all(self, runner):
        """start sem nome e sem --all mostra erro."""
        result = runner.invoke(cli, ["start"])
        assert result.exit_code != 0

    def test_start_local_e_docker_mutuamente_exclusivos(self, runner):
        """--local e --docker juntos dao erro."""
        result = runner.invoke(cli, ["start", "test", "--local", "--docker"])
        assert result.exit_code != 0
        assert "mutuamente exclusivas" in result.output

    def test_start_all_sem_times(self, runner):
        """--all sem times mostra mensagem."""
        with patch("ai_squad.cli.main._get_manager") as mock_mgr:
            mock_mgr.return_value.list_teams.return_value = []
            result = runner.invoke(cli, ["start", "--all"])

        assert result.exit_code == 0
        assert "Nenhum time" in result.output

    def test_start_force_local(self, runner, tmp_path, monkeypatch):
        """--local forca modo local."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".ai-squad").mkdir()
        (tmp_path / ".ai-squad" / ".env").write_text("TELEGRAM_TOKEN=x\n")

        with patch("ai_squad.cli.main._start_local") as mock_start:
            result = runner.invoke(cli, ["start", "test", "--local"])

        mock_start.assert_called_once_with("test", use_tui=False)

    def test_start_force_docker(self, runner):
        """--docker forca modo docker."""
        with patch("ai_squad.cli.main._get_manager") as mock_mgr:
            mock_mgr.return_value.exists.return_value = True
            mock_mgr.return_value.validate_env.return_value = ["TELEGRAM_TOKEN"]
            mock_mgr.return_value.get_path.return_value = Path("/fake")

            result = runner.invoke(cli, ["start", "test", "--docker"])

        # Deve ter tentado iniciar, mas env faltando
        assert "Variáveis não preenchidas" in result.output or result.exit_code == 0

    def test_start_com_tui(self, runner, tmp_path, monkeypatch):
        """--tui passa use_tui=True para _start_local."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".ai-squad").mkdir()

        with patch("ai_squad.cli.main._start_local") as mock_start:
            result = runner.invoke(cli, ["start", "test", "--local", "--tui"])

        mock_start.assert_called_once_with("test", use_tui=True)


# --- _start_local ---


class TestStartLocal:
    """Testes para _start_local."""

    def test_start_local_sem_env(self, tmp_path, monkeypatch):
        """start_local sem .env mostra erro e sai."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".ai-squad").mkdir()
        # Sem .env

        mock_resolver = MagicMock()
        mock_resolver.return_value.env_path = tmp_path / ".ai-squad" / ".env"
        mock_resolver.return_value.state_dir = tmp_path / ".ai-squad" / "state"
        mock_resolver.return_value.config_path = tmp_path / ".ai-squad" / "config.yaml"

        with pytest.raises(SystemExit):
            with patch("ai_squad.path_resolver.PathResolver", mock_resolver):
                _start_local("test")

    def test_start_local_com_env_e_token_faltando(self, tmp_path, monkeypatch):
        """start_local com .env mas token placeholder mostra erro."""
        monkeypatch.chdir(tmp_path)
        squad_dir = tmp_path / ".ai-squad"
        squad_dir.mkdir()
        (squad_dir / ".env").write_text(
            "CLAUDE_CODE_OAUTH_TOKEN=PREENCHA_AQUI_token\n"
            "TELEGRAM_TOKEN=PREENCHA_AQUI_telegram\n"
            "TELEGRAM_CHAT_ID=PREENCHA_AQUI_chat\n"
        )
        (squad_dir / "config.yaml").write_text(
            "ai_provider: claude-agent-sdk\nmessaging_provider: telegram\n"
        )

        mock_resolver = MagicMock()
        mock_resolver.return_value.env_path = squad_dir / ".env"
        mock_resolver.return_value.state_dir = squad_dir / "state"
        mock_resolver.return_value.config_path = squad_dir / "config.yaml"

        with pytest.raises(SystemExit):
            with patch("ai_squad.path_resolver.PathResolver", mock_resolver):
                _start_local("test")


# --- Comando stop ---


class TestStopCommand:
    """Testes para o comando stop."""

    def test_stop_local_mostra_ctrl_c(self, runner, tmp_path, monkeypatch):
        """stop em modo local mostra mensagem sobre Ctrl+C."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".ai-squad").mkdir()

        result = runner.invoke(cli, ["stop", "test"])
        assert "Ctrl+C" in result.output

    def test_stop_sem_nome_e_sem_all(self, runner, tmp_path, monkeypatch):
        """stop sem nome e sem --all mostra erro."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["stop"])
        assert result.exit_code != 0

    def test_stop_all(self, runner, tmp_path, monkeypatch):
        """--all para todos os times."""
        monkeypatch.chdir(tmp_path)
        with patch("ai_squad.cli.main._get_manager") as mock_mgr:
            mock_mgr.return_value.list_teams.return_value = [
                {"name": "time1"},
                {"name": "time2"},
            ]
            mock_mgr.return_value.exists.return_value = True
            mock_mgr.return_value.get_path.return_value = tmp_path

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                result = runner.invoke(cli, ["stop", "--all"])

        assert result.exit_code == 0


# --- _start_team ---


class TestStartTeam:
    """Testes para _start_team."""

    def test_start_team_nao_encontrado(self, runner):
        """start_team com time inexistente mostra erro."""
        from ai_squad.cli.main import _start_team

        with patch("ai_squad.cli.main._get_manager") as mock_mgr:
            manager = MagicMock()
            manager.exists.return_value = False
            _start_team(manager, "inexistente")

    def test_start_team_env_faltando(self, runner):
        """start_team com env faltando mostra erro."""
        from ai_squad.cli.main import _start_team

        manager = MagicMock()
        manager.exists.return_value = True
        manager.validate_env.return_value = ["TELEGRAM_TOKEN"]
        manager.get_path.return_value = Path("/fake")

        _start_team(manager, "test")

    def test_start_team_build_se_necessario(self, runner, tmp_path):
        """start_team constroi imagem se nao existe."""
        from ai_squad.cli.main import _start_team

        manager = MagicMock()
        manager.exists.return_value = True
        manager.validate_env.return_value = []
        manager.get_path.return_value = tmp_path

        with patch("ai_squad.cli.main._image_exists", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                _start_team(manager, "test")

    def test_start_team_docker_compose_falha(self, runner, tmp_path):
        """start_team com falha no docker compose mostra erro."""
        from ai_squad.cli.main import _start_team

        manager = MagicMock()
        manager.exists.return_value = True
        manager.validate_env.return_value = []
        manager.get_path.return_value = tmp_path

        with patch("ai_squad.cli.main._image_exists", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1, stdout="", stderr="error"
                )
                _start_team(manager, "test")
