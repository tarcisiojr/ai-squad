"""Implementação Telegram do barramento de mensageria."""

import asyncio
import logging
import os
from typing import Callable

from src.messaging.interface import MessageBus
from src.messaging.registry import register

logger = logging.getLogger("ai-squad.telegram")


class TelegramMessageBus(MessageBus):
    """Barramento de mensageria via Telegram.

    Suporta envio/recebimento de texto e voz (via Whisper API).
    Cada persona (PO, Dev, QA) pode ter seu próprio bot token.
    Apenas o chat_id autorizado (allowed_chat_id) pode interagir.
    Suporta Forum Topics para isolamento de demandas via thread_id.
    """

    def __init__(
        self,
        token: str = "",
        persona_name: str = "Agent",
        persona_avatar: str = "",
        whisper_api_key: str | None = None,
        allowed_chat_id: str = "",
        activation_mode: str = "mention",
    ) -> None:
        # Permite instanciar sem token (lê do env em start())
        self._token = token or os.environ.get("TELEGRAM_TOKEN", "")
        self._persona_name = persona_name
        self._persona_avatar = persona_avatar
        self._whisper_api_key = whisper_api_key
        self._allowed_chat_id = allowed_chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self._activation_mode = activation_mode
        self._bot_username: str = ""
        self._message_callback: Callable | None = None
        self._voice_callback: Callable | None = None
        self._photo_callback: Callable | None = None
        self._document_callback: Callable | None = None
        self._reaction_callback: Callable | None = None
        self._app = None
        self._pending_approvals: dict[str, asyncio.Future] = {}
        self._pending_text_reply: dict[str, asyncio.Future] = {}
        self._is_forum: bool = False

    # --- Ciclo de vida ---

    async def start(self) -> None:
        """Inicia o bot do Telegram: inicializa app + polling."""
        await self._ensure_app()
        assert self._app is not None

        # Detecta username do bot para filtragem de menções
        try:
            bot_info = await self._app.bot.get_me()
            self._bot_username = bot_info.username or ""
            logger.info("Bot username: @%s", self._bot_username)
        except Exception as e:
            logger.warning("Erro ao obter username do bot: %s", e)

        # Detecta modo fórum
        await self._detect_forum_mode()

        await self._app.initialize()
        await self._app.start()
        assert self._app.updater is not None
        await self._app.updater.start_polling()

    async def stop(self) -> None:
        """Para polling e encerra o bot gracefully."""
        if self._app is None:
            return
        if self._app.updater and self._app.updater.running:
            await self._app.updater.stop()
        if self._app.running:
            await self._app.stop()
        await self._app.shutdown()

    # --- Auto-descrição ---

    @classmethod
    def required_env_vars(cls) -> list[str]:
        """Variáveis obrigatórias para o Telegram."""
        return ["TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]

    @classmethod
    def env_template(cls) -> str:
        """Template de .env para Telegram."""
        return (
            "# Telegram Bot (criado via @BotFather)\n"
            "TELEGRAM_TOKEN=PREENCHA_AQUI_token_bot_telegram\n"
            "\n"
            "# Chat ID do Telegram (grupo ou chat privado)\n"
            "TELEGRAM_CHAT_ID=PREENCHA_AQUI_chat_id_telegram\n"
        )

    # --- Activation mode ---

    @property
    def bot_identifier(self) -> str:
        """Username do bot (@username)."""
        return self._bot_username

    def is_mention(self, message_data: dict) -> bool:
        """Verifica se a mensagem menciona o bot via entities do Telegram."""
        entities = message_data.get("entities", [])
        text = message_data.get("text", "")
        bot_username = self._bot_username.lower()
        if not bot_username:
            return True  # Sem username, não filtra

        for entity in entities:
            if entity.get("type") == "mention":
                offset = entity.get("offset", 0)
                length = entity.get("length", 0)
                mention = text[offset : offset + length].lower().lstrip("@")
                if mention == bot_username:
                    return True
            elif entity.get("type") == "text_mention":
                # Menção sem username (por ID)
                return True
        return False

    def is_dm(self, message_data: dict) -> bool:
        """Verifica se é chat privado (1:1)."""
        return message_data.get("chat_type") == "private"

    def _should_process(self, update) -> bool:
        """Decide se a mensagem deve ser processada conforme activation_mode."""
        if not update.message:
            return False

        chat_type = update.message.chat.type  # private, group, supergroup
        # DM sempre processa
        if chat_type == "private":
            return True

        # Pending reply — sempre captura
        chat_id = str(update.message.chat_id)
        thread_id = self._to_str_thread(update.message.message_thread_id)
        reply_key = f"{chat_id}:{thread_id}" if thread_id else chat_id
        if reply_key in self._pending_text_reply or chat_id in self._pending_text_reply:
            return True

        # Activation mode
        if self._activation_mode == "all":
            return True

        if self._activation_mode == "command":
            text = update.message.text or ""
            return text.strip().startswith("/")

        # mention (default)
        entities = update.message.entities or []
        text = update.message.text or ""
        bot_username = self._bot_username.lower()
        if not bot_username:
            return True  # Sem username conhecido, processa tudo

        for entity in entities:
            if entity.type == "mention":
                mention = text[entity.offset : entity.offset + entity.length].lower().lstrip("@")
                if mention == bot_username:
                    return True
            elif entity.type == "bot_command":
                return True
        return False

    # --- Capacidades ---

    @property
    def supports_threads(self) -> bool:
        """Retorna True se o chat é um grupo-fórum do Telegram."""
        return self._is_forum

    @property
    def default_chat_id(self) -> str:
        """Retorna o chat_id principal (allowed_chat_id)."""
        return self._allowed_chat_id

    # --- Internals ---

    def _to_int_thread(self, thread_id: str | None) -> int | None:
        """Converte thread_id str para int (formato interno do Telegram)."""
        if thread_id is None:
            return None
        try:
            return int(thread_id)
        except (ValueError, TypeError):
            return None

    def _to_str_thread(self, thread_id: int | None) -> str | None:
        """Converte thread_id int (Telegram) para str (interface genérica)."""
        if thread_id is None:
            return None
        return str(thread_id)

    def _is_authorized(self, chat_id: str) -> bool:
        """Verifica se o chat_id está autorizado a interagir com o bot."""
        if not self._allowed_chat_id:
            return True
        return chat_id == self._allowed_chat_id

    async def _detect_forum_mode(self) -> None:
        """Detecta se o chat configurado é um grupo-fórum do Telegram."""
        if not self._allowed_chat_id or not self._app:
            return
        try:
            chat = await self._app.bot.get_chat(self._allowed_chat_id)
            self._is_forum = bool(getattr(chat, "is_forum", False))
            if self._is_forum:
                logger.info("Modo fórum detectado para chat %s", self._allowed_chat_id)
            else:
                logger.info("Chat %s não é fórum — modo flat", self._allowed_chat_id)
        except Exception as e:
            logger.warning("Erro ao detectar modo fórum: %s", e)
            self._is_forum = False

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
            chat_id = str(update.message.chat_id)
            user_id = str(update.message.from_user.id) if update.message.from_user else chat_id
            thread_id = self._to_str_thread(update.message.message_thread_id)

            if not self._is_authorized(chat_id):
                logger.warning("Mensagem ignorada de chat_id nao autorizado: %s", chat_id)
                return

            # Filtro de activation_mode (antes de processar)
            if not self._should_process(update):
                return

            text = update.message.text

            # Mostra "digitando..." imediatamente
            try:
                await self._app.bot.send_chat_action(
                    chat_id=chat_id,
                    action="typing",
                    message_thread_id=update.message.message_thread_id,
                )
            except Exception:
                pass

            # Se ha uma pergunta pendente para este usuario, responde ela
            reply_key = f"{chat_id}:{thread_id}" if thread_id else chat_id
            if reply_key in self._pending_text_reply:
                self._pending_text_reply[reply_key].set_result(text)
                return

            # Fallback: chave sem thread para compatibilidade
            if chat_id in self._pending_text_reply:
                self._pending_text_reply[chat_id].set_result(text)
                return

            # Caso contrario, trata como nova demanda
            if self._message_callback:
                await self._message_callback(
                    text,
                    thread_id=thread_id,
                    user_id=user_id,
                )

        # Registra handler de mensagens de voz
        async def _handle_voice(update, context):
            if not update.message or not update.message.voice:
                return
            chat_id = str(update.message.chat_id)
            user_id = str(update.message.from_user.id) if update.message.from_user else chat_id
            thread_id = self._to_str_thread(update.message.message_thread_id)

            if not self._is_authorized(chat_id):
                logger.warning("Voz ignorada de chat_id nao autorizado: %s", chat_id)
                return
            if self._voice_callback:
                texto = await self._transcribe_voice(update, context)
                if texto:
                    await self._voice_callback(
                        texto,
                        thread_id=thread_id,
                        user_id=user_id,
                    )

        # Registra handler de callbacks (botões inline)
        async def _handle_callback(update, context):
            query = update.callback_query
            await query.answer()
            _user_id = str(query.from_user.id)  # noqa: F841 — disponível para uso futuro
            chat_id = str(query.message.chat_id)
            if not self._is_authorized(chat_id):
                logger.warning("Callback ignorado de chat_id nao autorizado: %s", chat_id)
                return
            key = f"{chat_id}:{query.message.message_id}"
            if key in self._pending_approvals:
                self._pending_approvals[key].set_result(query.data)

        # Registra handler de fotos
        async def _handle_photo(update, context):
            if not update.message or not update.message.photo:
                return
            chat_id = str(update.message.chat_id)
            user_id = str(update.message.from_user.id) if update.message.from_user else chat_id
            thread_id = self._to_str_thread(update.message.message_thread_id)

            if not self._is_authorized(chat_id):
                logger.warning("Foto ignorada de chat_id nao autorizado: %s", chat_id)
                return
            if not self._photo_callback:
                return

            import time as _time

            # Baixa a maior resolução disponível
            photo = update.message.photo[-1]
            file = await photo.get_file()
            suffix = f"telegram_photo_{int(_time.time())}.jpg"
            tmp_path = f"/tmp/{suffix}"
            await file.download_to_drive(tmp_path)

            caption = update.message.caption or "Analise esta imagem"
            await self._photo_callback(
                caption,
                tmp_path,
                thread_id=thread_id,
                user_id=user_id,
            )

        # Registra handler de documentos (PDF, DOCX, etc)
        async def _handle_document(update, context):
            if not update.message or not update.message.document:
                return
            chat_id = str(update.message.chat_id)
            user_id = str(update.message.from_user.id) if update.message.from_user else chat_id
            thread_id = self._to_str_thread(update.message.message_thread_id)

            if not self._is_authorized(chat_id):
                logger.warning("Documento ignorado de chat_id nao autorizado: %s", chat_id)
                return
            if not self._document_callback:
                return

            import time as _time

            doc = update.message.document
            file = await doc.get_file()
            original_name = doc.file_name or f"doc_{int(_time.time())}"
            suffix = original_name.split(".")[-1] if "." in original_name else "bin"
            tmp_path = f"/tmp/telegram_doc_{int(_time.time())}.{suffix}"
            await file.download_to_drive(tmp_path)

            caption = update.message.caption or f"Documento recebido: {original_name}"
            await self._document_callback(
                caption,
                tmp_path,
                thread_id=thread_id,
                user_id=user_id,
                original_filename=original_name,
            )

        # Registra handler de reações em mensagens
        async def _handle_reaction(update, context):
            reaction_update = update.message_reaction
            if not reaction_update:
                return
            chat_id = str(reaction_update.chat.id)
            if not self._is_authorized(chat_id):
                return
            if not self._reaction_callback:
                return

            msg_id = reaction_update.message_id
            user_id = str(reaction_update.user.id) if reaction_update.user else ""

            # Extrai emoji da nova reação
            new_reactions = reaction_update.new_reaction or []
            for reaction in new_reactions:
                emoji = getattr(reaction, "emoji", None)
                if emoji:
                    await self._reaction_callback(chat_id, msg_id, emoji, user_id)

        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text))
        self._app.add_handler(MessageHandler(filters.COMMAND, _handle_text))
        self._app.add_handler(MessageHandler(filters.VOICE, _handle_voice))
        self._app.add_handler(MessageHandler(filters.PHOTO, _handle_photo))
        self._app.add_handler(MessageHandler(filters.Document.ALL, _handle_document))
        self._app.add_handler(CallbackQueryHandler(_handle_callback))

        # Handler de reações (MessageReactionHandler disponível em python-telegram-bot 21+)
        try:
            from telegram.ext import MessageReactionHandler

            self._app.add_handler(MessageReactionHandler(_handle_reaction))
        except ImportError:
            logger.warning("MessageReactionHandler não disponível — reações desabilitadas")

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

    async def send_typing(self, chat_id: str, *, thread_id: str | None = None) -> None:
        """Envia acao 'digitando...' no Telegram."""
        await self._ensure_app()
        assert self._app is not None
        try:
            await self._app.bot.send_chat_action(
                chat_id=chat_id,
                action="typing",
                message_thread_id=self._to_int_thread(thread_id),
            )
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

    async def _send(self, chat_id: str, text: str, *, thread_id: str | None = None, **kwargs):
        """Envia mensagem com Markdown. Fallback para texto plano se falhar."""
        max_len = 4096
        if len(text) > max_len:
            parts = [text[i : i + max_len] for i in range(0, len(text), max_len)]
            msg = None
            for i, part in enumerate(parts):
                part_kwargs = kwargs if i == len(parts) - 1 else {}
                msg = await self._send(chat_id, part, thread_id=thread_id, **part_kwargs)
            return msg

        int_thread = self._to_int_thread(thread_id)
        assert self._app is not None
        # Tenta enviar com Markdown primeiro, fallback para texto plano
        try:
            return await self._app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                message_thread_id=int_thread,
                **kwargs,
            )
        except Exception:
            return await self._app.bot.send_message(
                chat_id=chat_id,
                text=text,
                message_thread_id=int_thread,
                **kwargs,
            )

    async def send_message(
        self, user_id: str, text: str, *, thread_id: str | None = None, **kwargs: str
    ) -> None:
        """Envia mensagem de texto via Telegram. Mostra 'digitando...' antes."""
        await self.send_typing(user_id, thread_id=thread_id)
        await self._ensure_app()
        sender = kwargs.pop("sender", "")
        if sender:
            prefixo = f"{sender}\n\n"
        elif self._persona_name:
            prefixo = f"{self._persona_avatar} {self._persona_name}\n\n"
        else:
            prefixo = ""
        await self._send(user_id, f"{prefixo}{text}", thread_id=thread_id)

    async def send_approval_request(
        self,
        user_id: str,
        question: str,
        options: list[str],
        *,
        thread_id: str | None = None,
    ) -> str:
        """Envia pedido de aprovação com botões inline."""
        await self._ensure_app()

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in options]
        reply_markup = InlineKeyboardMarkup(keyboard)

        prefixo = f"{self._persona_avatar} {self._persona_name}\n" if self._persona_name else ""
        msg = await self._send(
            user_id,
            f"{prefixo}{question}",
            thread_id=thread_id,
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

    async def ask_user(self, user_id: str, question: str, *, thread_id: str | None = None) -> str:
        """Envia pergunta e aguarda resposta de texto livre do usuário."""
        await self._ensure_app()

        # Usa chave com thread_id para isolar respostas por tópico
        reply_key = f"{user_id}:{thread_id}" if thread_id else user_id
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_text_reply[reply_key] = future

        if question:
            prefixo = f"{self._persona_avatar} {self._persona_name}\n" if self._persona_name else ""
            await self._send(user_id, f"{prefixo}{question}", thread_id=thread_id)

        try:
            resposta = await future
            return resposta
        finally:
            self._pending_text_reply.pop(reply_key, None)

    async def receive_message(self, callback: Callable) -> None:
        """Registra callback para mensagens de texto."""
        self._message_callback = callback

    async def receive_voice(self, callback: Callable) -> None:
        """Registra callback para mensagens de voz."""
        self._voice_callback = callback

    async def receive_photo(self, callback: Callable) -> None:
        """Registra callback para fotos (callback recebe texto, image_path, thread_id, user_id)."""
        self._photo_callback = callback

    async def send_photo(
        self,
        user_id: str,
        photo_path: str,
        caption: str = "",
        *,
        thread_id: str | None = None,
    ) -> None:
        """Envia foto via Telegram."""
        await self._ensure_app()
        assert self._app is not None
        try:
            with open(photo_path, "rb") as f:
                await self._app.bot.send_photo(
                    chat_id=user_id,
                    photo=f,
                    caption=caption or None,
                    message_thread_id=self._to_int_thread(thread_id),
                )
        except Exception as e:
            import logging

            logging.getLogger("ai-squad.telegram").error("Erro ao enviar foto: %s", e)
            # Fallback: informa que nao conseguiu enviar
            await self.send_message(
                user_id, f"Nao consegui enviar a imagem: {e}", thread_id=thread_id
            )

    async def create_thread(self, chat_id: str, title: str) -> str | None:
        """Cria Forum Topic no Telegram e retorna o thread_id como string."""
        await self._ensure_app()
        assert self._app is not None
        try:
            # Limita título a 128 caracteres (limite do Telegram)
            title = title[:128]
            result = await self._app.bot.create_forum_topic(
                chat_id=chat_id,
                name=title,
            )
            thread_id = result.message_thread_id
            logger.info("Forum Topic criado: '%s' (thread_id=%d)", title, thread_id)
            return str(thread_id)
        except Exception as e:
            logger.error("Erro ao criar Forum Topic '%s': %s", title, e)
            return None

    async def receive_document(self, callback: Callable) -> None:
        """Registra callback para documentos (PDF, DOCX, etc)."""
        self._document_callback = callback

    async def on_reaction(self, callback: Callable) -> None:
        """Registra callback para reações em mensagens."""
        self._reaction_callback = callback

    async def notify(self, user_id: str, text: str, *, thread_id: str | None = None) -> None:
        """Envia notificação via Telegram."""
        await self.send_message(user_id, f"🔔 {text}", thread_id=thread_id)


# Auto-registro no registry
register("telegram", TelegramMessageBus)
