"""Modelos e enums compartilhados da plataforma."""

from enum import Enum


class AgentStatus(Enum):
    """Status possíveis de um agente IA."""

    IDLE = "idle"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    ERROR = "error"
    DONE = "done"
