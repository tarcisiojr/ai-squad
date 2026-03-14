"""Implementação do adapter de IA para Claude Code CLI."""

import asyncio
import json
import subprocess
from typing import Callable

from src.adapters.interface import AIAgentAdapter
from src.models import AgentStatus


class ClaudeCodeAdapter(AIAgentAdapter):
    """Adapter que executa Claude Code via subprocess CLI.

    Usa `claude --print` para execução não-interativa.
    Funciona com a assinatura Claude Code existente do usuário.
    """

    def __init__(
        self,
        timeout: int = 300,
        working_dir: str | None = None,
    ) -> None:
        self._timeout = timeout
        self._working_dir = working_dir
        self._status = AgentStatus.IDLE
        self._human_needed_callback: Callable | None = None

    async def run(self, prompt: str, context: dict) -> str:
        """Executa Claude Code com prompt via subprocess."""
        self._status = AgentStatus.RUNNING

        try:
            # Monta o prompt completo com contexto
            prompt_completo = self._build_prompt(prompt, context)

            resultado = await asyncio.to_thread(
                self._execute_subprocess, prompt_completo
            )

            self._status = AgentStatus.DONE
            return resultado

        except subprocess.TimeoutExpired:
            self._status = AgentStatus.ERROR
            raise TimeoutError(
                f"Claude Code excedeu timeout de {self._timeout}s"
            )
        except subprocess.CalledProcessError as e:
            self._status = AgentStatus.ERROR
            raise RuntimeError(
                f"Claude Code retornou erro (código {e.returncode}): {e.stderr}"
            )
        except FileNotFoundError:
            self._status = AgentStatus.ERROR
            raise RuntimeError(
                "Claude Code CLI não encontrado. "
                "Verifique se está instalado e no PATH."
            )

    def _build_prompt(self, prompt: str, context: dict) -> str:
        """Monta prompt completo incluindo contexto."""
        partes = []

        if context:
            partes.append("## Contexto")
            for chave, valor in context.items():
                partes.append(f"- {chave}: {valor}")
            partes.append("")

        partes.append("## Tarefa")
        partes.append(prompt)

        return "\n".join(partes)

    def _execute_subprocess(self, prompt: str) -> str:
        """Executa o subprocess do Claude Code CLI."""
        cmd = ["claude", "--print"]

        resultado = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=self._timeout,
            cwd=self._working_dir,
        )

        if resultado.returncode != 0:
            raise subprocess.CalledProcessError(
                resultado.returncode,
                cmd,
                output=resultado.stdout,
                stderr=resultado.stderr,
            )

        return resultado.stdout.strip()

    async def ask(self, question: str) -> str:
        """Faz uma pergunta ao Claude Code."""
        return await self.run(question, {})

    def status(self) -> AgentStatus:
        """Retorna o status atual do adapter."""
        return self._status

    def on_human_needed(self, callback: Callable) -> None:
        """Registra callback para intervenção humana."""
        self._human_needed_callback = callback

    async def request_human_approval(self, question: str) -> str:
        """Solicita aprovação humana via callback registrado."""
        if self._human_needed_callback is None:
            raise RuntimeError(
                "Nenhum callback registrado para intervenção humana"
            )

        self._status = AgentStatus.WAITING_HUMAN
        resultado = await self._human_needed_callback(question)
        self._status = AgentStatus.RUNNING
        return resultado
