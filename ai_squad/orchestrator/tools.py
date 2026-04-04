"""Modelos de dados para agentes em execução."""

import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("ai-squad.tools")


@dataclass
class AgentSession:
    """Sessão persistente de um agente entre delegações da mesma demanda.

    Permite reutilizar contexto já carregado em vez de reconstruir do zero.
    Identificada por agent_name--demand_id. Expira por TTL de inatividade.
    """

    session_id: str  # "agent_name--demand_id"
    agent_name: str
    demand_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    context_loaded: bool = False  # True após primeira delegação com contexto completo
    turn_count: int = 0
    ttl: int = 300  # 5 minutos de inatividade

    @property
    def is_expired(self) -> bool:
        """Verifica se a sessão expirou por inatividade."""
        return (time.time() - self.last_active) > self.ttl

    def touch(self) -> None:
        """Atualiza timestamp de última atividade."""
        self.last_active = time.time()
        self.turn_count += 1


class SessionManager:
    """Gerencia sessões de agentes com TTL e invalidação.

    Permite que agentes reutilizem contexto entre delegações
    da mesma demanda, economizando tokens de reconstrução.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, AgentSession] = {}

    @staticmethod
    def _make_key(agent_name: str, demand_id: str) -> str:
        return f"{agent_name}--{demand_id}"

    def get_or_create(self, agent_name: str, demand_id: str) -> tuple[AgentSession, bool]:
        """Retorna sessão existente ou cria nova.

        Returns:
            Tupla (sessão, is_new). is_new=True se criou nova sessão.
        """
        key = self._make_key(agent_name, demand_id)
        session = self._sessions.get(key)

        if session and not session.is_expired:
            session.touch()
            return session, False

        # Sessão nova ou expirada
        if session:
            logger.info(
                "Sessão expirada descartada: %s (TTL: %ds, inativo: %ds)",
                key,
                session.ttl,
                int(time.time() - session.last_active),
            )

        session = AgentSession(
            session_id=key,
            agent_name=agent_name,
            demand_id=demand_id,
        )
        self._sessions[key] = session
        return session, True

    def invalidate(self, agent_name: str, demand_id: str) -> None:
        """Remove sessão específica."""
        key = self._make_key(agent_name, demand_id)
        removed = self._sessions.pop(key, None)
        if removed:
            logger.info("Sessão invalidada: %s", key)

    def invalidate_demand(self, demand_id: str) -> None:
        """Remove todas as sessões de uma demanda (ex: nova demanda)."""
        keys_to_remove = [k for k, s in self._sessions.items() if s.demand_id == demand_id]
        for key in keys_to_remove:
            del self._sessions[key]
        if keys_to_remove:
            logger.info("Sessões invalidadas para demanda %s: %d", demand_id, len(keys_to_remove))

    def cleanup_expired(self) -> int:
        """Remove todas as sessões expiradas. Retorna quantidade removida."""
        expired = [k for k, s in self._sessions.items() if s.is_expired]
        for key in expired:
            del self._sessions[key]
        return len(expired)

    @property
    def active_count(self) -> int:
        """Número de sessões ativas (não expiradas)."""
        return sum(1 for s in self._sessions.values() if not s.is_expired)


@dataclass
class RunningAgent:
    """Agente em execucao background."""

    agent_name: str
    demand_id: str
    user_id: str = ""
    thread_id: str | None = None
    task: asyncio.Task[str] | None = None
    started_at: float = field(default_factory=time.time)
    status: str = "running"  # running, done, error, incomplete
    result: str | None = None
    error: str | None = None
    retries: int = 0
    progress_log: list[str] = field(default_factory=lambda: list[str]())

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
