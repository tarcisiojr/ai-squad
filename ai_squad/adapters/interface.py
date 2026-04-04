"""Interface abstrata do adapter de agente IA."""

from abc import ABC, abstractmethod
from typing import Any

from ai_squad.common.events import CallbackRegistry
from ai_squad.models import AgentStatus


class AIAgentAdapter(ABC):
    """Adapter abstrato para execução de agentes IA.

    Define o contrato para interação com providers de IA
    independente da implementação concreta.

    Usa CallbackRegistry para registro de callbacks:
        adapter.on("progress", handler)
        adapter.emit("progress", agent_name, message)
    """

    def __init__(self) -> None:
        self._callbacks = CallbackRegistry()

    def on(self, event: str, callback: Any) -> None:
        """Registra callback para um evento."""
        self._callbacks.on(event, callback)

    def emit(self, event: str, *args: Any, **kwargs: Any) -> Any:
        """Invoca callback registrado. Retorna None se não registrado."""
        return self._callbacks.emit(event, *args, **kwargs)

    @abstractmethod
    async def run(self, prompt: str, context: dict[str, Any]) -> str:
        """Executa o agente com o prompt e contexto fornecidos."""
        ...

    @abstractmethod
    async def ask(self, question: str) -> str:
        """Faz uma pergunta ao agente e retorna a resposta."""
        ...

    @abstractmethod
    def status(self) -> AgentStatus:
        """Retorna o status atual do agente."""
        ...

    @abstractmethod
    def on_human_needed(self, callback: Any) -> None:
        """Registra callback para quando intervenção humana é necessária."""
        ...

    async def shutdown(self) -> None:
        """Libera recursos do adapter. No-op por padrão."""
