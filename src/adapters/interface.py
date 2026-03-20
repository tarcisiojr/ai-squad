"""Interface abstrata do adapter de agente IA."""

from abc import ABC, abstractmethod
from typing import Callable

from src.models import AgentStatus


class AIAgentAdapter(ABC):
    """Adapter abstrato para execução de agentes IA.

    Define o contrato para interação com providers de IA
    independente da implementação concreta.
    """

    @abstractmethod
    async def run(self, prompt: str, context: dict) -> str:
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
    def on_human_needed(self, callback: Callable) -> None:
        """Registra callback para quando intervenção humana é necessária."""
        ...

    async def shutdown(self) -> None:
        """Libera recursos do adapter. No-op por padrão."""
        pass

    # Callbacks opcionais — no-op por padrão, adapter concreto sobrescreve
    def set_progress_callback(self, callback: Callable) -> None:
        pass

    def set_start_agent_callback(self, callback: Callable) -> None:
        pass

    def set_get_agents_callback(self, callback: Callable) -> None:
        pass

    def set_get_demand_state_callback(self, callback: Callable) -> None:
        pass

    def set_read_journal_callback(self, callback: Callable) -> None:
        pass

    def set_send_image_callback(self, callback: Callable) -> None:
        pass

    def set_learn_lesson_callback(self, callback: Callable) -> None:
        pass

    def set_get_pipeline_state_callback(self, callback: Callable) -> None:
        pass

    def set_advance_step_callback(self, callback: Callable) -> None:
        pass

    def set_skip_step_callback(self, callback: Callable) -> None:
        pass

    def set_rerun_step_callback(self, callback: Callable) -> None:
        pass
