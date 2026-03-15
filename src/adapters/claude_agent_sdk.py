"""Implementação do adapter de IA usando Claude Agent SDK."""

import asyncio
from pathlib import Path
from typing import Callable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    query,
)

from src.adapters.interface import AIAgentAdapter
from src.models import AgentStatus


class ClaudeAgentSDKAdapter(AIAgentAdapter):
    """Adapter que executa Claude via Agent SDK in-process.

    Usa o claude-agent-sdk para execução nativa async com streaming
    de mensagens, sem overhead de subprocess.
    """

    def __init__(
        self,
        timeout: int = 300,
        working_dir: str | None = None,
        model: str | None = None,
    ) -> None:
        self._timeout = timeout
        self._working_dir = working_dir
        self._model = model
        self._status = AgentStatus.IDLE
        self._human_needed_callback: Callable | None = None

    async def run(self, prompt: str, context: dict) -> str:
        """Executa Claude Agent SDK com prompt e contexto."""
        self._status = AgentStatus.RUNNING

        try:
            prompt_completo = self._build_prompt(prompt, context)
            resultado = await self._execute_sdk(prompt_completo)
            self._status = AgentStatus.DONE
            return resultado

        except asyncio.TimeoutError:
            self._status = AgentStatus.ERROR
            raise TimeoutError(
                f"Claude Agent SDK excedeu timeout de {self._timeout}s"
            )
        except Exception as e:
            self._status = AgentStatus.ERROR
            raise RuntimeError(f"Erro no Claude Agent SDK: {e}") from e

    async def _execute_sdk(self, prompt: str) -> str:
        """Executa query via SDK e coleta mensagens de texto."""
        options = self._build_options()

        partes_texto: list[str] = []

        async with asyncio.timeout(self._timeout):
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            partes_texto.append(block.text)

        return "\n".join(partes_texto).strip()

    def _build_options(self) -> ClaudeAgentOptions:
        """Constrói opções do SDK a partir da configuração."""
        kwargs: dict = {
            "max_turns": 10,
        }

        if self._working_dir:
            kwargs["cwd"] = Path(self._working_dir)

        if self._model:
            kwargs["model"] = self._model

        return ClaudeAgentOptions(**kwargs)

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

    async def ask(self, question: str) -> str:
        """Faz uma pergunta ao Claude Agent SDK."""
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
