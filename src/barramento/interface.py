"""Interface abstrata do barramento de mensageria."""

from abc import ABC, abstractmethod
from typing import Callable


class MessageBus(ABC):
    """Barramento de mensageria abstrato.

    Define o contrato para envio e recebimento de mensagens
    entre o orquestrador e o usuário humano.
    """

    @abstractmethod
    async def send_message(self, user_id: str, text: str) -> None:
        """Envia mensagem de texto ao usuário."""
        ...

    @abstractmethod
    async def send_approval_request(
        self, user_id: str, question: str, options: list[str]
    ) -> str:
        """Envia pedido de aprovação com opções e retorna a escolha."""
        ...

    @abstractmethod
    async def receive_message(self, callback: Callable) -> None:
        """Registra callback para recebimento de mensagens de texto."""
        ...

    @abstractmethod
    async def receive_voice(self, callback: Callable) -> None:
        """Registra callback para recebimento de mensagens de voz."""
        ...

    @abstractmethod
    async def notify(self, user_id: str, text: str) -> None:
        """Envia notificação ao usuário."""
        ...
