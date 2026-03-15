"""Implementação Telegram do barramento de mensageria."""

import asyncio
from typing import Callable

from src.barramento.interface import MessageBus


class TelegramMessageBus(MessageBus):
    """Barramento de mensageria via Telegram.

    Suporta envio/recebimento de texto e voz (via Whisper API).
    Cada persona (PO, Dev, QA) pode ter seu próprio bot token.
    """

    def __init__(
        self,
        token: str,
        persona_name: str = "Agent",
        persona_avatar: str = "",
        whisper_api_key: str | None = None,
    ) -> None:
        self._token = token
        self._persona_name = persona_name
        self._persona_avatar = persona_avatar
        self._whisper_api_key = whisper_api_key
        self._message_callback: Callable | None = None
        self._voice_callback: Callable | None = None
        self._app = None
        self._pending_approvals: dict[str, asyncio.Future] = {}
        self._pending_text_reply: dict[str, asyncio.Future] = {}

    async def _ensure_app(self):
        """Inicializa o bot do Telegram sob demanda."""
        if self._app is not None:
            return

        try:
            from telegram.ext import (
                ApplicationBuilder,
                MessageHandler,
                CallbackQueryHandler,
                filters,
            )
        except ImportError:
            raise ImportError(
                "python-telegram-bot é necessário. "
                "Instale com: pip install python-telegram-bot"
            )

        self._app = (
            ApplicationBuilder()
            .token(self._token)
            .build()
        )

        # Registra handler de mensagens de texto
        async def _handle_text(update, context):
            if not update.message:
                return
            user_id = str(update.message.chat_id)
            text = update.message.text

            # Se há uma pergunta pendente para este usuário, responde ela
            if user_id in self._pending_text_reply:
                self._pending_text_reply[user_id].set_result(text)
                return

            # Caso contrário, trata como nova demanda
            if self._message_callback:
                await self._message_callback(text)

        # Registra handler de mensagens de voz
        async def _handle_voice(update, context):
            if self._voice_callback and update.message and update.message.voice:
                texto = await self._transcribe_voice(update, context)
                if texto:
                    await self._voice_callback(texto)

        # Registra handler de callbacks (botões inline)
        async def _handle_callback(update, context):
            query = update.callback_query
            await query.answer()
            user_id = str(query.from_user.id)
            key = f"{user_id}:{query.message.message_id}"
            if key in self._pending_approvals:
                self._pending_approvals[key].set_result(query.data)

        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text))
        self._app.add_handler(MessageHandler(filters.VOICE, _handle_voice))
        self._app.add_handler(CallbackQueryHandler(_handle_callback))

    async def _transcribe_voice(self, update, context) -> str | None:
        """Transcreve áudio via Whisper API."""
        if not self._whisper_api_key:
            return None

        try:
            import openai

            voice = update.message.voice
            file = await context.bot.get_file(voice.file_id)
            audio_bytes = await file.download_as_bytearray()

            # Salva temporariamente para enviar ao Whisper
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                client = openai.OpenAI(api_key=self._whisper_api_key)
                with open(tmp_path, "rb") as audio_file:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                    )
                return transcription.text
            finally:
                os.unlink(tmp_path)

        except Exception:
            return None

    async def send_message(self, user_id: str, text: str) -> None:
        """Envia mensagem de texto via Telegram."""
        await self._ensure_app()
        prefixo = f"{self._persona_avatar} *{self._persona_name}*\n" if self._persona_name else ""
        await self._app.bot.send_message(
            chat_id=user_id,
            text=f"{prefixo}{text}",
            parse_mode="Markdown",
        )

    async def send_approval_request(
        self, user_id: str, question: str, options: list[str]
    ) -> str:
        """Envia pedido de aprovação com botões inline."""
        await self._ensure_app()

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = [
            [InlineKeyboardButton(opt, callback_data=opt)] for opt in options
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        prefixo = f"{self._persona_avatar} *{self._persona_name}*\n" if self._persona_name else ""
        msg = await self._app.bot.send_message(
            chat_id=user_id,
            text=f"{prefixo}{question}",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

        # Aguarda resposta via callback
        key = f"{user_id}:{msg.message_id}"
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_approvals[key] = future

        try:
            resultado = await future
            return resultado
        finally:
            self._pending_approvals.pop(key, None)

    async def ask_user(self, user_id: str, question: str) -> str:
        """Envia pergunta e aguarda resposta de texto livre do usuário."""
        await self._ensure_app()
        prefixo = f"{self._persona_avatar} *{self._persona_name}*\n" if self._persona_name else ""
        await self._app.bot.send_message(
            chat_id=user_id,
            text=f"{prefixo}{question}",
            parse_mode="Markdown",
        )

        # Registra future para capturar próxima mensagem de texto deste usuário
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_text_reply[user_id] = future

        try:
            resposta = await future
            return resposta
        finally:
            self._pending_text_reply.pop(user_id, None)

    async def receive_message(self, callback: Callable) -> None:
        """Registra callback para mensagens de texto."""
        self._message_callback = callback

    async def receive_voice(self, callback: Callable) -> None:
        """Registra callback para mensagens de voz."""
        self._voice_callback = callback

    async def notify(self, user_id: str, text: str) -> None:
        """Envia notificação via Telegram."""
        await self.send_message(user_id, f"🔔 {text}")
