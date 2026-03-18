"""Implementação Telegram do barramento de mensageria."""

import asyncio
from typing import Callable

from src.messaging.interface import MessageBus


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
                CallbackQueryHandler,
                MessageHandler,
                filters,
            )
        except ImportError:
            raise ImportError(
                "python-telegram-bot é necessário. Instale com: pip install python-telegram-bot"
            )

        self._app = ApplicationBuilder().token(self._token).build()

        # Registra handler de mensagens de texto
        async def _handle_text(update, context):
            if not update.message:
                return
            user_id = str(update.message.chat_id)
            text = update.message.text

            # Mostra "digitando..." imediatamente
            try:
                await self._app.bot.send_chat_action(chat_id=user_id, action="typing")  # type: ignore[union-attr]
            except Exception:
                pass

            # Se ha uma pergunta pendente para este usuario, responde ela
            if user_id in self._pending_text_reply:
                self._pending_text_reply[user_id].set_result(text)
                return

            # Caso contrario, trata como nova demanda
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
        self._app.add_handler(MessageHandler(filters.COMMAND, _handle_text))
        self._app.add_handler(MessageHandler(filters.VOICE, _handle_voice))
        self._app.add_handler(CallbackQueryHandler(_handle_callback))

    # URL do serviço Whisper separado (container dedicado)
    WHISPER_SERVICE_URL = "http://whisper:8000/transcribe"

    async def _transcribe_voice(self, update, context) -> str | None:
        """Transcreve audio via servico Whisper separado (HTTP)."""
        try:
            voice = update.message.voice
            file = await context.bot.get_file(voice.file_id)
            audio_bytes = await file.download_as_bytearray()

            import aiohttp  # type: ignore[import-not-found]

            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field(
                    "file",
                    audio_bytes,
                    filename="audio.ogg",
                    content_type="audio/ogg",
                )
                async with session.post(
                    self.WHISPER_SERVICE_URL,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("text", "").strip() or None
                    else:
                        import logging

                        logging.getLogger("ai-squad.telegram").error(
                            "Whisper retornou %d: %s",
                            resp.status,
                            await resp.text(),
                        )
                        return None

        except Exception as e:
            import logging

            logging.getLogger("ai-squad.telegram").error("Erro na transcricao: %s", e)
            return None

    async def send_typing(self, chat_id: str) -> None:
        """Envia acao 'digitando...' no Telegram."""
        await self._ensure_app()
        assert self._app is not None
        try:
            await self._app.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass

    @staticmethod
    def _escape_markdown_v2(text: str) -> str:
        """Escapa caracteres especiais do MarkdownV2, preservando formatacao basica."""
        import re

        # Preserva negrito (**texto**) e italico (_texto_) convertendo para MarkdownV2
        # Primeiro protege as formatacoes existentes
        protected = []

        def protect(match):
            protected.append(match.group(0))
            return f"\x00PROT{len(protected) - 1}\x00"

        # Protege **negrito** e *italico* e `codigo`
        result = re.sub(r"\*\*(.+?)\*\*", protect, text)
        result = re.sub(r"\*(.+?)\*", protect, result)
        result = re.sub(r"`(.+?)`", protect, result)

        # Escapa caracteres especiais do MarkdownV2
        special_chars = r"_[]()~>#+=|{}.!-"
        for char in special_chars:
            result = result.replace(char, f"\\{char}")

        # Restaura formatacoes protegidas
        for i, original in enumerate(protected):
            result = result.replace(f"\x00PROT{i}\x00", original)

        return result

    async def _send(self, chat_id: str, text: str, **kwargs):
        """Envia mensagem com Markdown. Fallback para texto plano se falhar."""
        max_len = 4096
        if len(text) > max_len:
            parts = [text[i : i + max_len] for i in range(0, len(text), max_len)]
            msg = None
            for i, part in enumerate(parts):
                part_kwargs = kwargs if i == len(parts) - 1 else {}
                msg = await self._send(chat_id, part, **part_kwargs)
            return msg

        assert self._app is not None
        # Tenta enviar com Markdown primeiro, fallback para texto plano
        try:
            return await self._app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                **kwargs,
            )
        except Exception:
            return await self._app.bot.send_message(
                chat_id=chat_id,
                text=text,
                **kwargs,
            )

    async def send_message(self, user_id: str, text: str, sender: str = "") -> None:
        """Envia mensagem de texto via Telegram. Mostra 'digitando...' antes."""
        await self.send_typing(user_id)
        await self._ensure_app()
        if sender:
            prefixo = f"{sender}\n\n"
        elif self._persona_name:
            prefixo = f"{self._persona_avatar} {self._persona_name}\n\n"
        else:
            prefixo = ""
        await self._send(user_id, f"{prefixo}{text}")

    async def send_approval_request(self, user_id: str, question: str, options: list[str]) -> str:
        """Envia pedido de aprovação com botões inline."""
        await self._ensure_app()

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in options]
        reply_markup = InlineKeyboardMarkup(keyboard)

        prefixo = f"{self._persona_avatar} {self._persona_name}\n" if self._persona_name else ""
        msg = await self._send(
            user_id,
            f"{prefixo}{question}",
            reply_markup=reply_markup,
        )

        assert msg is not None, "Falha ao enviar mensagem de aprovação"
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

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_text_reply[user_id] = future

        prefixo = f"{self._persona_avatar} {self._persona_name}\n" if self._persona_name else ""
        await self._send(user_id, f"{prefixo}{question}")

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

    async def send_photo(self, user_id: str, photo_path: str, caption: str = "") -> None:
        """Envia foto via Telegram."""
        await self._ensure_app()
        assert self._app is not None
        try:
            with open(photo_path, "rb") as f:
                await self._app.bot.send_photo(
                    chat_id=user_id,
                    photo=f,
                    caption=caption or None,
                )
        except Exception as e:
            import logging

            logging.getLogger("ai-squad.telegram").error("Erro ao enviar foto: %s", e)
            # Fallback: informa que nao conseguiu enviar
            await self.send_message(user_id, f"Nao consegui enviar a imagem: {e}")

    async def notify(self, user_id: str, text: str) -> None:
        """Envia notificação via Telegram."""
        await self.send_message(user_id, f"🔔 {text}")
