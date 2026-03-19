"""Modelos de dados para agentes em execução."""

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class RunningAgent:
    """Agente em execucao background."""

    agent_name: str
    demand_id: str
    user_id: str = ""
    thread_id: str | None = None
    task: asyncio.Task | None = None
    started_at: float = field(default_factory=time.time)
    status: str = "running"  # running, done, error, incomplete
    result: str | None = None
    error: str | None = None
    retries: int = 0

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_at

    def elapsed_str(self) -> str:
        secs = int(self.elapsed)
        if secs < 60:
            return f"{secs}s"
        mins = secs // 60
        rest = secs % 60
        if rest:
            return f"{mins}min{rest}s"
        return f"{mins}min"
