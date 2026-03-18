"""Interface abstrata do barramento de mensageria."""

from abc import ABC, abstractmethod
from typing import Callable


class MessageBus(ABC):
    """Barramento de mensageria abstrato.

    Define o contrato para envio e recebimento de mensagens
    entre o orquestrador e o usuário humano.
    Suporta thread_id para isolamento de demandas via Forum Topics.
    """

    @abstractmethod
    async def send_message(
        self, user_id: str, text: str, *, thread_id: int | None = None, **kwargs: str
    ) -> None:
        """Envia mensagem de texto ao usuário."""
        ...

    @abstractmethod
    async def send_approval_request(
        self,
        user_id: str,
        question: str,
        options: list[str],
        *,
        thread_id: int | None = None,
    ) -> str:
        """Envia pedido de aprovação com opções e retorna a escolha."""
        ...

    @abstractmethod
    async def ask_user(self, user_id: str, question: str, *, thread_id: int | None = None) -> str:
        """Envia pergunta ao usuário e aguarda resposta de texto livre."""
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
    async def notify(self, user_id: str, text: str, *, thread_id: int | None = None) -> None:
        """Envia notificação ao usuário."""
        ...

    async def send_photo(
        self,
        user_id: str,
        photo_path: str,
        caption: str = "",
        *,
        thread_id: int | None = None,
    ) -> None:
        """Envia imagem ao usuário. Opcional — implementações sem suporte ignoram."""

    async def send_typing(self, user_id: str, *, thread_id: int | None = None) -> None:
        """Envia indicador de digitação. Opcional — implementações sem suporte ignoram."""

    async def create_thread(self, chat_id: str, title: str) -> int | None:
        """Cria tópico/thread no canal. Retorna thread_id ou None se não suportado."""
        return None

    async def receive_document(self, callback: Callable) -> None:
        """Registra callback para recebimento de documentos (PDF, DOCX, etc).

        Opcional — implementações sem suporte ignoram.
        Callback recebe: (caption, file_path, thread_id, user_id).
        """

    async def on_reaction(self, callback: Callable) -> None:
        """Registra callback para reações em mensagens.

        Opcional — implementações sem suporte ignoram.
        Callback recebe: (chat_id, message_id, emoji, user_id).
        """
