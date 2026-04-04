"""Sistema de eventos com callback registry."""

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("ai-squad.events")

# Constantes de eventos — usar em vez de strings literais
EVENT_PROGRESS = "progress"
EVENT_START_AGENT = "start_agent"
EVENT_GET_AGENTS = "get_agents"
EVENT_GET_DEMAND_STATE = "get_demand_state"
EVENT_READ_JOURNAL = "read_journal"
EVENT_SEND_IMAGE = "send_image"
EVENT_LEARN_LESSON = "learn_lesson"
EVENT_GET_PIPELINE_STATE = "get_pipeline_state"
EVENT_ADVANCE_STEP = "advance_step"
EVENT_SKIP_STEP = "skip_step"
EVENT_RERUN_STEP = "rerun_step"
EVENT_QUERY_GRAPH = "query_graph"
EVENT_HUMAN_NEEDED = "human_needed"


class CallbackRegistry:
    """Registry de callbacks baseado em dict.

    Substitui campos individuais + setters por registro centralizado.
    """

    def __init__(self) -> None:
        self._callbacks: dict[str, Callable[..., Any]] = {}

    def on(self, event: str, callback: Callable[..., Any]) -> None:
        """Registra callback para um evento."""
        self._callbacks[event] = callback

    def emit(self, event: str, *args: Any, **kwargs: Any) -> Any:
        """Invoca callback registrado. Retorna None se não registrado."""
        cb = self._callbacks.get(event)
        if cb is None:
            return None
        return cb(*args, **kwargs)

    def has(self, event: str) -> bool:
        """Verifica se existe callback registrado para o evento."""
        return event in self._callbacks
