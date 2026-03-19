"""Implementação Google Chat do barramento de mensageria."""

import asyncio
import logging
import os
import uuid
from typing import Callable

from src.messaging.interface import MessageBus
from src.messaging.registry import register

logger = logging.getLogger("ai-squad.gchat")

# Intervalo de polling padrão (segundos)
DEFAULT_POLL_INTERVAL = 3
# Tamanho máximo de mensagem no Google Chat
MAX_MESSAGE_LENGTH = 4096


class GChatMessageBus(MessageBus):
    """Barramento de mensageria via Google Chat.

    Usa Service Account para autenticação e polling para receber mensagens.
    Suporta threads em Spaces via threadKey.
    """

    def __init__(self, **kwargs) -> None:
        self._credentials_path = os.environ.get("GCHAT_CREDENTIALS_PATH", "")
        self._space_id = os.environ.get("GCHAT_SPACE_ID", "")
        self._poll_interval = int(os.environ.get("GCHAT_POLL_INTERVAL", str(DEFAULT_POLL_INTERVAL)))
        self._persona_name = kwargs.get("persona_name", "Agent")
        self._persona_avatar = kwargs.get("persona_avatar", "")
        self._service = None
        self._bot_id: str = ""
        self._message_callback: Callable | None = None
        self._voice_callback: Callable | None = None
        self._poll_task: asyncio.Task | None = None
        self._running = False
        # Timestamp ISO da última mensagem processada
        self._last_seen: str = ""
        # Futures para aguardar respostas de texto (ask_user/approval)
        self._pending_text_reply: dict[str, asyncio.Future] = {}

    # --- Ciclo de vida ---

    async def start(self) -> None:
        """Inicia polling do Google Chat."""
        self._build_service()
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("GChat polling iniciado (space: %s, intervalo: %ds)", self._space_id, self._poll_interval)

    async def stop(self) -> None:
        """Para o polling."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("GChat polling parado")

    # --- Auto-descrição ---

    @classmethod
    def required_env_vars(cls) -> list[str]:
        """Variáveis obrigatórias para o Google Chat."""
        return ["GCHAT_CREDENTIALS_PATH", "GCHAT_SPACE_ID"]

    @classmethod
    def env_template(cls) -> str:
        """Template de .env para Google Chat."""
        return (
            "# Google Chat — Service Account (JSON credentials)\n"
            "GCHAT_CREDENTIALS_PATH=PREENCHA_AQUI_caminho_credentials_json\n"
            "\n"
            "# Space ID do Google Chat (ex: spaces/AAAAxxxxxx)\n"
            "GCHAT_SPACE_ID=PREENCHA_AQUI_space_id\n"
            "\n"
            "# Intervalo de polling em segundos (opcional, default: 3)\n"
            "# GCHAT_POLL_INTERVAL=3\n"
        )

    # --- Capacidades ---

    @property
    def supports_threads(self) -> bool:
        """Google Chat Spaces sempre suportam threads."""
        return True

    @property
    def default_chat_id(self) -> str:
        """Retorna o Space ID configurado."""
        return self._space_id

    # --- Internals ---

    def _build_service(self) -> None:
        """Cria o client da Google Chat API via Service Account."""
        if self._service is not None:
            return

        try:
            import googleapiclient.discovery
            from google.oauth2 import service_account
        except ImportError:
            raise ImportError(
                "google-auth e google-api-python-client são necessários. "
                "Instale com: pip install google-auth google-api-python-client"
            )

        scopes = ["https://www.googleapis.com/auth/chat.bot"]
        credentials = service_account.Credentials.from_service_account_file(
            self._credentials_path, scopes=scopes
        )
        self._service = googleapiclient.discovery.build(
            "chat", "v1", credentials=credentials, cache_discovery=False
        )

        # Valida conexão com um request inicial
        try:
            self._service.spaces().messages().list(
                parent=self._format_space(), pageSize=1
            ).execute()
        except Exception:
            pass

        logger.info("Google Chat API client inicializado")

    def _format_space(self) -> str:
        """Retorna space_id no formato correto (spaces/XXX)."""
        if self._space_id.startswith("spaces/"):
            return self._space_id
        return f"spaces/{self._space_id}"

    async def _poll_loop(self) -> None:
        """Loop de polling que busca novas mensagens no Space."""
        while self._running:
            try:
                messages = await asyncio.to_thread(self._fetch_new_messages)
                for msg in messages:
                    await self._process_message(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Erro no polling GChat: %s", e)

            await asyncio.sleep(self._poll_interval)

    def _fetch_new_messages(self) -> list[dict]:
        """Busca mensagens novas no Space (síncrono — chamado via to_thread)."""
        if not self._service:
            return []

        try:
            kwargs = {
                "parent": self._format_space(),
                "pageSize": 25,
            }
            # Filtra por createTime se já vimos alguma mensagem
            if self._last_seen:
                kwargs["filter"] = f'createTime > "{self._last_seen}"'

            result = self._service.spaces().messages().list(**kwargs).execute()
            messages = result.get("messages", [])

            # Ordena por createTime para processar na ordem
            messages.sort(key=lambda m: m.get("createTime", ""))

            return messages
        except Exception as e:
            logger.warning("Falha ao listar mensagens GChat: %s", e)
            return []

    async def _process_message(self, msg: dict) -> None:
        """Processa uma mensagem recebida do polling."""
        # Atualiza timestamp
        create_time = msg.get("createTime", "")
        if create_time > self._last_seen:
            self._last_seen = create_time

        # Ignora mensagens do próprio bot
        sender = msg.get("sender", {})
        if sender.get("type") == "BOT":
            return

        text = msg.get("text", "").strip()
        if not text:
            return

        user_id = sender.get("name", "")  # users/XXXXX
        # Extrai thread_id do thread name
        thread = msg.get("thread", {})
        thread_name = thread.get("name", "")
        # Thread name: spaces/XXX/threads/YYY → usamos como thread_id
        thread_id = thread_name if thread_name else None

        # Verifica se há uma pergunta pendente para este usuário/thread
        reply_key = f"{self._space_id}:{thread_id}" if thread_id else self._space_id
        if reply_key in self._pending_text_reply:
            self._pending_text_reply[reply_key].set_result(text)
            return

        # Fallback: chave sem thread
        if self._space_id in self._pending_text_reply:
            self._pending_text_reply[self._space_id].set_result(text)
            return

        # Nova mensagem → callback
        if self._message_callback:
            await self._message_callback(
                text,
                thread_id=thread_id,
                user_id=user_id,
            )

    # --- Interface MessageBus ---

    async def send_message(
        self, user_id: str, text: str, *, thread_id: str | None = None, **kwargs: str
    ) -> None:
        """Envia mensagem de texto via Google Chat."""
        if not self._service:
            self._build_service()

        sender = kwargs.pop("sender", "")
        if sender:
            prefixo = f"{sender}\n\n"
        elif self._persona_name:
            prefixo = f"{self._persona_avatar} {self._persona_name}\n\n"
        else:
            prefixo = ""

        full_text = f"{prefixo}{text}"

        # Split de mensagens longas
        if len(full_text) > MAX_MESSAGE_LENGTH:
            parts = [full_text[i : i + MAX_MESSAGE_LENGTH] for i in range(0, len(full_text), MAX_MESSAGE_LENGTH)]
            for part in parts:
                await self._send_text(part, thread_id=thread_id)
            return

        await self._send_text(full_text, thread_id=thread_id)

    async def _send_text(self, text: str, *, thread_id: str | None = None) -> dict | None:
        """Envia texto ao Space (internal)."""
        body: dict = {"text": text}

        if thread_id:
            body["thread"] = {"name": thread_id}

        try:
            kwargs: dict = {
                "parent": self._format_space(),
                "body": body,
            }
            if thread_id:
                kwargs["messageReplyOption"] = "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"

            result = await asyncio.to_thread(
                self._service.spaces().messages().create(**kwargs).execute
            )
            return result
        except Exception as e:
            logger.error("Erro ao enviar mensagem GChat: %s", e)
            return None

    async def send_approval_request(
        self,
        user_id: str,
        question: str,
        options: list[str],
        *,
        thread_id: str | None = None,
    ) -> str:
        """Envia Card v2 visual com opções numeradas e aguarda resposta por texto."""
        # Monta Card v2 visual
        buttons = [
            {
                "text": f"{i + 1}. {opt}",
                "disabled": True,
            }
            for i, opt in enumerate(options)
        ]

        card_body: dict = {
            "text": f"{self._persona_avatar} {self._persona_name}\n\nDigite o número da opção:",
            "cardsV2": [
                {
                    "cardId": f"approval-{uuid.uuid4().hex[:8]}",
                    "card": {
                        "header": {"title": "Aprovação necessária"},
                        "sections": [
                            {
                                "widgets": [
                                    {"textParagraph": {"text": question}},
                                    {"buttonList": {"buttons": buttons}},
                                ],
                            }
                        ],
                    },
                }
            ],
        }

        if thread_id:
            card_body["thread"] = {"name": thread_id}

        # Envia card
        try:
            kwargs: dict = {
                "parent": self._format_space(),
                "body": card_body,
            }
            if thread_id:
                kwargs["messageReplyOption"] = "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"

            await asyncio.to_thread(
                self._service.spaces().messages().create(**kwargs).execute
            )
        except Exception as e:
            logger.error("Erro ao enviar card de aprovação: %s", e)
            # Fallback: envia como texto
            text_options = "\n".join(f"  {i + 1}. {opt}" for i, opt in enumerate(options))
            await self.send_message(
                user_id,
                f"{question}\n\n{text_options}\n\nDigite o número da opção:",
                thread_id=thread_id,
            )

        # Aguarda resposta por texto
        reply_key = f"{self._space_id}:{thread_id}" if thread_id else self._space_id
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_text_reply[reply_key] = future

        try:
            resposta = await future
            # Converte número para opção
            try:
                indice = int(resposta.strip()) - 1
                if 0 <= indice < len(options):
                    return options[indice]
            except ValueError:
                pass
            # Se não é número, retorna texto raw (pode ser a opção digitada)
            return resposta
        finally:
            self._pending_text_reply.pop(reply_key, None)

    async def ask_user(self, user_id: str, question: str, *, thread_id: str | None = None) -> str:
        """Envia pergunta e aguarda resposta de texto livre."""
        reply_key = f"{self._space_id}:{thread_id}" if thread_id else self._space_id
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_text_reply[reply_key] = future

        if question:
            await self.send_message(user_id, question, thread_id=thread_id)

        try:
            resposta = await future
            return resposta
        finally:
            self._pending_text_reply.pop(reply_key, None)

    async def receive_message(self, callback: Callable) -> None:
        """Registra callback para mensagens de texto."""
        self._message_callback = callback

    async def receive_voice(self, callback: Callable) -> None:
        """Registra callback para voz (não suportado no GChat — no-op)."""
        self._voice_callback = callback

    async def notify(self, user_id: str, text: str, *, thread_id: str | None = None) -> None:
        """Envia notificação via Google Chat."""
        await self.send_message(user_id, f"🔔 {text}", thread_id=thread_id)

    async def create_thread(self, chat_id: str, title: str) -> str | None:
        """Cria thread no Space via threadKey gerado."""
        thread_key = uuid.uuid4().hex[:12]

        # Envia mensagem inaugural na thread
        body: dict = {
            "text": f"📌 {title}",
            "thread": {"threadKey": thread_key},
        }

        try:
            result = await asyncio.to_thread(
                self._service.spaces().messages().create(
                    parent=self._format_space(),
                    body=body,
                    messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
                ).execute
            )
            # Retorna o thread name completo (spaces/XXX/threads/YYY)
            thread_name = result.get("thread", {}).get("name", "")
            logger.info("Thread criada no GChat: '%s' (key=%s)", title, thread_key)
            return thread_name or None
        except Exception as e:
            logger.error("Erro ao criar thread GChat '%s': %s", title, e)
            return None


# Auto-registro no registry
register("gchat", GChatMessageBus)
