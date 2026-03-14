"""Testes para execução de agentes via Docker."""

from unittest.mock import patch, MagicMock

import pytest

from src.orchestrator.docker import DockerAgentRunner


class TestDockerAgentRunner:
    """Testes para DockerAgentRunner."""

    @pytest.fixture
    def runner(self):
        """Cria instância de DockerAgentRunner."""
        return DockerAgentRunner(image="test-image:latest")

    def test_configuracao_padrao(self):
        """Verifica configuração padrão."""
        runner = DockerAgentRunner()
        assert runner._image == "ai-dev-platform:latest"
        assert runner._network == "none"

    def test_run_agent_sucesso(self, runner):
        """Verifica execução de agente com sucesso."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "resultado isolado"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            resultado = runner.run_agent(
                agent_path="/tmp/agent",
                prompt="Executar tarefa",
            )

        assert resultado == "resultado isolado"
        # Verifica que foi chamado com flags de isolamento
        cmd = mock_run.call_args[0][0]
        assert "--network" in cmd
        assert "none" in cmd
        assert "--read-only" in cmd
        assert "--memory" in cmd

    def test_run_agent_com_working_dir(self, runner):
        """Verifica que working_dir é montado."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            runner.run_agent(
                agent_path="/tmp/agent",
                prompt="tarefa",
                working_dir="/tmp/workspace",
            )

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "/tmp/workspace:/workspace:rw" in cmd_str

    def test_run_agent_falha(self, runner):
        """Verifica tratamento de falha do container."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "erro no container"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="Container falhou"):
                runner.run_agent("/tmp/agent", "tarefa")

    def test_isolamento_rede_none(self, runner):
        """Verifica que container é executado sem rede."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            runner.run_agent("/tmp/agent", "tarefa")

        cmd = mock_run.call_args[0][0]
        # Verifica flags de segurança
        idx_network = cmd.index("--network")
        assert cmd[idx_network + 1] == "none"

    def test_isolamento_read_only(self, runner):
        """Verifica que filesystem é read-only."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            runner.run_agent("/tmp/agent", "tarefa")

        cmd = mock_run.call_args[0][0]
        assert "--read-only" in cmd

    def test_isolamento_limite_memoria(self, runner):
        """Verifica limite de memória."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            runner.run_agent("/tmp/agent", "tarefa")

        cmd = mock_run.call_args[0][0]
        idx_memory = cmd.index("--memory")
        assert cmd[idx_memory + 1] == "512m"

    def test_is_docker_available_true(self, runner):
        """Verifica detecção de Docker disponível."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            assert runner.is_docker_available() is True

    def test_is_docker_available_false(self, runner):
        """Verifica detecção quando Docker não está disponível."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            assert runner.is_docker_available() is False

    def test_agente_nao_acessa_filesystem_host(self, runner):
        """Verifica que agente é montado como read-only."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            runner.run_agent(
                agent_path="/host/agents/po",
                prompt="tarefa",
            )

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        # Agent path montado como read-only
        assert "/host/agents/po:/agent:ro" in cmd_str
        # Filesystem read-only
        assert "--read-only" in cmd
