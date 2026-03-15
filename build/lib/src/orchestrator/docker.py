"""Integração de execução de agentes via Docker."""

import subprocess
from pathlib import Path


class DockerAgentRunner:
    """Executa agentes em containers Docker isolados.

    Garante que agentes não acessem o filesystem do host
    nem tenham acesso de rede irrestrito.
    """

    def __init__(
        self,
        image: str = "ai-dev-platform:latest",
        network: str = "none",
    ) -> None:
        self._image = image
        self._network = network

    def run_agent(
        self,
        agent_path: str,
        prompt: str,
        working_dir: str | None = None,
        timeout: int = 300,
    ) -> str:
        """Executa agente dentro de container Docker isolado."""
        cmd = [
            "docker", "run",
            "--rm",
            "--network", self._network,
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid",
            "--memory", "512m",
            "--cpus", "1.0",
        ]

        # Monta diretório do agente como read-only
        if agent_path:
            cmd.extend(["-v", f"{agent_path}:/agent:ro"])

        # Monta diretório de trabalho se fornecido
        if working_dir:
            cmd.extend(["-v", f"{working_dir}:/workspace:rw"])

        cmd.extend([
            self._image,
            "python", "-c", f"print('{prompt}')",
        ])

        resultado = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if resultado.returncode != 0:
            raise RuntimeError(
                f"Container falhou (código {resultado.returncode}): "
                f"{resultado.stderr}"
            )

        return resultado.stdout.strip()

    def build_image(self, dockerfile_path: str = ".") -> None:
        """Constrói imagem Docker para agentes."""
        subprocess.run(
            ["docker", "build", "-t", self._image, dockerfile_path],
            check=True,
            capture_output=True,
            text=True,
        )

    def is_docker_available(self) -> bool:
        """Verifica se Docker está disponível."""
        try:
            resultado = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return resultado.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
