# Design: add-gchat-provider

## Visão Geral

Implementar `GChatMessageBus` seguindo o mesmo padrão do `TelegramMessageBus`: herda de `MessageBus`, auto-registra no registry, encapsula toda lógica de API internamente.

## Autenticação

```python
from google.oauth2 import service_account
import googleapiclient.discovery

SCOPES = ["https://www.googleapis.com/auth/chat.bot"]
creds = service_account.Credentials.from_service_account_file(
    os.environ["GCHAT_CREDENTIALS_PATH"], scopes=SCOPES
)
service = googleapiclient.discovery.build("chat", "v1", credentials=creds)
```

## Envio de Mensagens

```python
# Texto simples
service.spaces().messages().create(
    parent="spaces/SPACE_ID",
    body={"text": "Olá!"},
).execute()

# Em thread existente
service.spaces().messages().create(
    parent="spaces/SPACE_ID",
    body={
        "text": "Resposta na thread",
        "thread": {"threadKey": "abc-123"},
    },
    messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD",
).execute()
```

## Recebimento via Polling

```
┌─────────────────────────────────────────────────┐
│              Polling Loop (asyncio)              │
│                                                  │
│  while running:                                  │
│    messages = spaces.messages.list(              │
│        parent=space_id,                          │
│        filter=f'createTime > "{last_seen}"'      │
│    )                                             │
│    for msg in messages:                          │
│        if msg.sender != bot_id:                  │
│            callback(msg.text, thread_id, user)   │
│    sleep(POLL_INTERVAL)                          │
│                                                  │
└─────────────────────────────────────────────────┘
```

- `last_seen` é timestamp ISO da última mensagem processada
- Filtra por `createTime` para pegar só novas
- Ignora mensagens do próprio bot (sender.type == "BOT")
- Usa `asyncio.to_thread()` para chamadas síncronas da API Google

## Aprovações via Cards v2

```python
card_message = {
    "cardsV2": [{
        "cardId": f"approval-{uuid}",
        "card": {
            "header": {"title": "Aprovação"},
            "sections": [{
                "widgets": [
                    {"textParagraph": {"text": question}},
                    {"buttonList": {
                        "buttons": [
                            {
                                "text": option,
                                "onClick": {"action": {
                                    "function": "approval_response",
                                    "parameters": [
                                        {"key": "approval_id", "value": approval_id},
                                        {"key": "choice", "value": option},
                                    ],
                                }},
                            }
                            for option in options
                        ]
                    }},
                ],
            }],
        },
    }],
}
```

Para capturar respostas dos botões:
- Polling verifica mensagens com `actionResponse` (interações de card)
- Alternativa simples: bot pede resposta por texto (fallback sem cards interativos)
- **Decisão**: começar com fallback por texto (mais simples, funciona sem webhook). Cards interativos exigem webhook ou Pub/Sub para receber CARD_CLICKED.

### Aprovação simplificada (v1)

Envia Card v2 visual + pede resposta por texto:
```
[Card com opções numeradas]
"Digite 1 para Aprovar, 2 para Rejeitar"
```
Bot espera próxima mensagem do usuário como resposta.

## Threads

- `create_thread()` gera UUID como threadKey
- `supports_threads` = True (Spaces sempre suportam)
- `send_message()` com `thread_id` usa `thread.threadKey`

## Estrutura do Arquivo

```python
# src/messaging/gchat.py (~250 linhas)

class GChatMessageBus(MessageBus):
    def __init__(self, **kwargs)

    # Ciclo de vida
    async def start()      # inicia polling loop
    async def stop()       # para polling

    # Auto-descrição
    @classmethod required_env_vars()
    @classmethod env_template()
    @property default_chat_id
    @property supports_threads

    # Internals
    def _build_service()           # cria google api client
    async def _poll_loop()         # loop de polling
    async def _process_message()   # processa msg recebida

    # Interface MessageBus
    async def send_message()
    async def send_approval_request()
    async def ask_user()
    async def receive_message()
    async def receive_voice()
    async def notify()
    async def create_thread()

register("gchat", GChatMessageBus)
```

## Decisões

1. **Polling, não Pub/Sub** — zero infra extra, delay de ~3s aceitável
2. **Aprovação por texto, não por CARD_CLICKED** — Cards interativos exigem webhook/Pub/Sub; na v1 usamos texto numerado
3. **Cards v2 para visual** — aprovações são enviadas como Card bonito + instrução de texto
4. **asyncio.to_thread** — API Google é síncrona, wrappa em thread para não bloquear
5. **Dependências opcionais** — `google-auth` e `google-api-python-client` só importados quando provider é gchat
