"""Contexto de mensagem para roteamento entre daemon, engine e callbacks."""

from dataclasses import dataclass


@dataclass
class MessageContext:
    """Encapsula informações de roteamento de uma mensagem.

    Distingue chat_id (onde) de user_id (quem) e inclui
    thread_id para suporte a Forum Topics do Telegram.
    """

    chat_id: str
    user_id: str
    thread_id: int | None = None
    demand_id: str | None = None
