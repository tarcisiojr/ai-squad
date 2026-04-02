"""Implementação Google Chat do barramento de mensageria."""

import asyncio
import logging
import os
import uuid
from typing import Callable

from ai_squad.messaging.interface import MessageBus
from ai_squad.messaging.registry import register

logger = logging.getLogger("ai-squad.gchat")

# Intervalo de polling padrão (segundos)
DEFAULT_POLL_INTERVAL = 3
# Tamanho máximo de mensagem no Google Chat
MAX_MESSAGE_LENGTH = 4096


class GChatMessageBus(MessageBus):
    """Barramento de mensageria via Google Chat.

    Suporta dois modos de autenticação:
    - Service Account (GCHAT_CREDENTIALS_PATH aponta para JSON de service account)
    - OAuth Client (GCHAT_CREDENTIALS_PATH aponta para JSON de OAuth client)

    No modo OAuth, o token é salvo em GCHAT_TOKEN_PATH (default: token_gchat.json
    no mesmo diretório do credentials). Na primeira execução, abre o navegador
    para autorização.
    """

    def __init__(self, **kwargs) -> None:
        self._credentials_path = os.environ.get("GCHAT_CREDENTIALS_PATH", "")
        self._space_id = os.environ.get("GCHAT_SPACE_ID", "")
        self._token_path = os.environ.get("GCHAT_TOKEN_PATH", "")
        self._poll_interval = int(os.environ.get("GCHAT_POLL_INTERVAL", str(DEFAULT_POLL_INTERVAL)))
        self._persona_name = kwargs.get("persona_name", "Agent")
        self._persona_avatar = kwargs.get("persona_avatar", "")
        self._activation_mode = kwargs.get("activation_mode", "mention")
        self._service = None
        self._bot_id: str = ""
        # Indica se autenticação é OAuth (usuário) ou Service Account (bot)
        self._is_oauth: bool = False
        # ID do usuário autenticado (para ignorar próprias mensagens no modo OAuth)
        self._authenticated_user_id: str = ""
        # Prefixos de persona para filtrar mensagens do próprio bot (modo same-account)
        self._own_prefixes: list[str] = []
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
        logger.info(
            "GChat polling iniciado (space: %s, intervalo: %ds)",
            self._space_id,
            self._poll_interval,
        )

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
            "# Google Chat — Credenciais (Service Account OU OAuth Client JSON)\n"
            "# Service Account: JSON com 'type: service_account'\n"
            "# OAuth Client: JSON baixado de 'OAuth 2.0 Client IDs' no Google Cloud\n"
            "GCHAT_CREDENTIALS_PATH=PREENCHA_AQUI_caminho_credentials_json\n"
            "\n"
            "# Space ID do Google Chat (ex: spaces/AAAAxxxxxx)\n"
            "GCHAT_SPACE_ID=PREENCHA_AQUI_space_id\n"
            "\n"
            "# (OAuth Client) Caminho para salvar token — opcional, default: token_gchat.json\n"
            "# GCHAT_TOKEN_PATH=\n"
            "\n"
            "# (OAuth Client) Email do usuário autenticado — para ignorar próprias mensagens\n"
            "# Detectado automaticamente, mas pode ser definido manualmente\n"
            "# GCHAT_USER_ID=seu-email@empresa.com\n"
            "\n"
            "# Intervalo de polling em segundos (opcional, default: 3)\n"
            "# GCHAT_POLL_INTERVAL=3\n"
        )

    # --- Activation mode ---

    @property
    def bot_identifier(self) -> str:
        """Identificador do bot no GChat."""
        return self._bot_id

    def is_mention(self, message_data: dict) -> bool:
        """Verifica se a mensagem menciona o bot via annotations do GChat.

        No modo Service Account: procura menções do tipo BOT.
        No modo OAuth: procura menção ao usuário autenticado (por email ou user ID).
        """
        annotations = message_data.get("annotations", [])
        for ann in annotations:
            if ann.get("type") == "USER_MENTION":
                user_mention = ann.get("userMention", {})
                # Modo Service Account — menção ao bot
                if user_mention.get("type") == "BOT":
                    return True
                # Modo OAuth — menção ao usuário autenticado
                if self._is_oauth and self._authenticated_user_id:
                    mentioned_user = user_mention.get("user", {})
                    if (
                        mentioned_user.get("email") == self._authenticated_user_id
                        or mentioned_user.get("name") == self._authenticated_user_id
                    ):
                        return True
        return False

    def is_dm(self, message_data: dict) -> bool:
        """Verifica se é DM. No GChat, espaços tipo DM têm spaceType DM."""
        return message_data.get("space_type") == "DIRECT_MESSAGE"

    def _should_process_msg(self, msg: dict) -> bool:
        """Decide se a mensagem deve ser processada conforme activation_mode."""
        # Pending reply — sempre captura
        thread = msg.get("thread", {})
        thread_name = thread.get("name", "")
        thread_id = thread_name if thread_name else None
        reply_key = f"{self._space_id}:{thread_id}" if thread_id else self._space_id
        if reply_key in self._pending_text_reply or self._space_id in self._pending_text_reply:
            return True

        # Modo all — processa tudo
        if self._activation_mode == "all":
            return True

        # Modo command — só mensagens com /
        if self._activation_mode == "command":
            text = msg.get("text", "").strip()
            return text.startswith("/")

        # Modo mention (default) — verifica annotations
        return self.is_mention(msg)

    # --- Registro de personas ---

    def register_personas(self, personas: dict) -> None:
        """Registra prefixos de persona para filtrar mensagens do próprio bot.

        No modo OAuth com mesma conta, o bot envia mensagens como o usuário.
        Os prefixos (ex: '👨‍💼 Squad Lead', '⚙️ Dev Backend') permitem distinguir
        mensagens do bot das mensagens reais do usuário.
        """
        prefixes = []
        for persona in personas.values():
            avatar = getattr(persona, "avatar", "")
            name = getattr(persona, "name", "")
            if avatar and name:
                prefixes.append(f"{avatar} {name}")
            elif name:
                prefixes.append(name)
        # Inclui o prefixo do próprio bus (persona_name/avatar do construtor)
        if self._persona_name:
            bus_prefix = f"{self._persona_avatar} {self._persona_name}".strip()
            if bus_prefix not in prefixes:
                prefixes.append(bus_prefix)
        self._own_prefixes = prefixes
        logger.info("Prefixos de persona registrados: %s", prefixes)

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
        """Cria o client da Google Chat API.

        Detecta automaticamente o tipo de credencial:
        - Service Account: campo "type": "service_account" no JSON
        - OAuth Client: campo "installed" ou "web" no JSON
        """
        if self._service is not None:
            return

        try:
            import googleapiclient.discovery
        except ImportError:
            raise ImportError(
                "google-api-python-client é necessário. "
                "Instale com: pip install google-api-python-client"
            )

        import json

        with open(self._credentials_path) as f:
            creds_data = json.load(f)

        if creds_data.get("type") == "service_account":
            credentials = self._auth_service_account(creds_data)
            self._is_oauth = False
        elif "installed" in creds_data or "web" in creds_data:
            credentials = self._auth_oauth_client()
            self._is_oauth = True
        else:
            raise ValueError(
                "Formato de credencial não reconhecido. "
                "Use Service Account JSON ou OAuth Client JSON do Google Cloud Console."
            )

        self._service = googleapiclient.discovery.build(
            "chat", "v1", credentials=credentials, cache_discovery=False
        )

        # No modo OAuth, descobre o ID do usuário autenticado para filtrar mensagens
        if self._is_oauth:
            self._discover_authenticated_user(credentials)

        # Valida conexão com um request inicial
        try:
            self._service.spaces().messages().list(
                parent=self._format_space(), pageSize=1
            ).execute()
        except Exception:
            pass

        auth_mode = "OAuth Client" if self._is_oauth else "Service Account"
        logger.info("Google Chat API client inicializado (modo: %s)", auth_mode)

    def _discover_authenticated_user(self, credentials) -> None:
        """Descobre o ID do usuário autenticado via People API ou token info.

        Necessário no modo OAuth para ignorar mensagens enviadas pelo próprio agente.
        """
        # Tenta via variável de ambiente (override manual)
        env_user = os.environ.get("GCHAT_USER_ID", "")
        if env_user:
            self._authenticated_user_id = env_user
            logger.info("Usuário autenticado (env): %s", self._authenticated_user_id)
            return

        # Tenta obter via token info (email do usuário)
        try:
            if hasattr(credentials, "service_account_email"):
                self._authenticated_user_id = credentials.service_account_email
            elif hasattr(credentials, "token"):
                import googleapiclient.discovery

                oauth2 = googleapiclient.discovery.build(
                    "oauth2", "v2", credentials=credentials, cache_discovery=False
                )
                user_info = oauth2.userinfo().get().execute()
                self._authenticated_user_id = user_info.get("email", "")
            logger.info("Usuário autenticado: %s", self._authenticated_user_id)
        except Exception as e:
            logger.warning(
                "Não foi possível descobrir usuário autenticado: %s. "
                "Defina GCHAT_USER_ID no .env para evitar loop de mensagens.",
                e,
            )

    def _auth_service_account(self, creds_data: dict):  # noqa: ANN201
        """Autenticação via Service Account."""
        from google.oauth2 import service_account

        scopes = ["https://www.googleapis.com/auth/chat.bot"]
        return service_account.Credentials.from_service_account_info(creds_data, scopes=scopes)

    def _auth_oauth_client(self):  # noqa: ANN201
        """Autenticação via OAuth Client com fluxo de autorização do usuário.

        Na primeira execução, abre o navegador para consentimento.
        O token é salvo em disco para reutilização.
        """
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            raise ImportError(
                "google-auth-oauthlib é necessário para OAuth Client. "
                "Instale com: pip install google-auth-oauthlib"
            )

        # Scopes para leitura e escrita no Google Chat como usuário
        scopes = [
            "https://www.googleapis.com/auth/chat.spaces.readonly",
            "https://www.googleapis.com/auth/chat.messages",
            "https://www.googleapis.com/auth/chat.messages.readonly",
        ]

        # Caminho do token persistido
        token_path = self._token_path
        if not token_path:
            from pathlib import Path

            token_path = str(Path(self._credentials_path).parent / "token_gchat.json")

        credentials = None

        # Tenta carregar token salvo
        if os.path.exists(token_path):
            credentials = Credentials.from_authorized_user_file(token_path, scopes)

        # Renova ou solicita novo token
        if credentials and credentials.expired and credentials.refresh_token:
            logger.info("Renovando token OAuth do Google Chat...")
            credentials.refresh(Request())
        elif not credentials or not credentials.valid:
            logger.info("Iniciando fluxo de autorização OAuth — abrindo navegador...")
            flow = InstalledAppFlow.from_client_secrets_file(self._credentials_path, scopes)
            credentials = flow.run_local_server(port=0)
            logger.info("Autorização OAuth concluída com sucesso")

        # Salva token para reutilização
        with open(token_path, "w") as f:
            f.write(credentials.to_json())

        return credentials

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

        # No modo OAuth (mesma conta), ignora mensagens que começam com prefixo de persona
        if self._is_oauth and self._own_prefixes:
            for prefix in self._own_prefixes:
                if text.startswith(prefix):
                    return
        if not text:
            return

        # Filtro de activation_mode
        if not self._should_process_msg(msg):
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
            parts = [
                full_text[i : i + MAX_MESSAGE_LENGTH]
                for i in range(0, len(full_text), MAX_MESSAGE_LENGTH)
            ]
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

            await asyncio.to_thread(self._service.spaces().messages().create(**kwargs).execute)
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
                self._service.spaces()
                .messages()
                .create(
                    parent=self._format_space(),
                    body=body,
                    messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
                )
                .execute
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
