"""Implementação CLI do barramento de mensageria para testes locais."""

import asyncio
from typing import Callable

from src.barramento.interface import MessageBus


class CLIMessageBus(MessageBus):
    """Barramento de mensageria via stdin/stdout.

    Usado para testes locais sem dependência do Telegram.
    """

    def __init__(self) -> None:
        self._message_callback: Callable | None = None
        self._voice_callback: Callable | None = None

    async def send_message(self, user_id: str, text: str) -> None:
        """Exibe mensagem no stdout."""
        print(f"[{user_id}] {text}")

    async def send_approval_request(self, user_id: str, question: str, options: list[str]) -> str:
        """Solicita aprovação via stdin com opções numeradas."""
        print(f"\n[Aprovação para {user_id}] {question}")
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")

        while True:
            try:
                resposta = await asyncio.to_thread(input, "Escolha (número): ")
                indice = int(resposta) - 1
                if 0 <= indice < len(options):
                    return options[indice]
                print(f"Opção inválida. Escolha entre 1 e {len(options)}.")
            except ValueError:
                print("Digite um número válido.")

    async def ask_user(self, user_id: str, question: str) -> str:
        """Solicita resposta de texto livre via stdin."""
        print(f"\n[Pergunta para {user_id}] {question}")
        resposta = await asyncio.to_thread(input, "Sua resposta: ")
        return resposta

    async def receive_message(self, callback: Callable) -> None:
        """Registra callback para mensagens de texto."""
        self._message_callback = callback

    async def receive_voice(self, callback: Callable) -> None:
        """Registra callback para mensagens de voz (não suportado no CLI)."""
        self._voice_callback = callback

    async def notify(self, user_id: str, text: str) -> None:
        """Exibe notificação no stdout."""
        print(f"[NOTIFICAÇÃO - {user_id}] {text}")

    async def process_input(self, text: str) -> None:
        """Processa input simulado (útil para testes)."""
        if self._message_callback:
            await self._message_callback(text)
