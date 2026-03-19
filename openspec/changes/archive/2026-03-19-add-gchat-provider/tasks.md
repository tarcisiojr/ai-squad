# Tasks: add-gchat-provider

## Fase 1: Implementação do Provider

- [x] Criar `src/messaging/gchat.py`
  - Classe `GChatMessageBus(MessageBus)`
  - Construtor com kwargs (compatível com daemon)
  - `_build_service()`: cria google api client com Service Account
  - `start()`: inicia polling loop via `asyncio.create_task`
  - `stop()`: cancela polling task
  - `required_env_vars()`: `["GCHAT_CREDENTIALS_PATH", "GCHAT_SPACE_ID"]`
  - `env_template()`: template com placeholders GChat
  - `default_chat_id`: retorna space_id do env
  - `supports_threads`: True

- [x] Implementar polling loop
  - `_poll_loop()`: loop com `spaces.messages.list()` via `asyncio.to_thread`
  - Filtro por `createTime` > último timestamp visto
  - Ignora mensagens do próprio bot (sender.type == "BOT")
  - Chama `_message_callback` com texto, thread_id, user_id
  - Intervalo configurável (default 3s)

- [x] Implementar envio de mensagens
  - `send_message()`: `spaces.messages.create()` com texto + prefixo persona
  - Suporte a `thread_id` via `thread.threadKey` + `messageReplyOption`
  - Split de mensagens longas (>4096 chars)
  - `notify()`: prefixo com emoji de notificação

- [x] Implementar aprovações
  - `send_approval_request()`: envia Card v2 visual + texto numerado
  - Aguarda resposta por texto do usuário (mesma lógica de `ask_user`)
  - `ask_user()`: envia pergunta e aguarda próxima mensagem via pending future

- [x] Implementar threads
  - `create_thread()`: gera UUID como threadKey, retorna string
  - `receive_message()` / `receive_voice()`: registra callbacks

- [x] Auto-registro no registry
  - `register("gchat", GChatMessageBus)` no final do arquivo
  - Adicionar import em `registry.py` → `load_builtin_providers()`

## Fase 2: Dependências

- [x] Adicionar `google-auth` e `google-api-python-client` como dependências opcionais no `pyproject.toml`

## Fase 3: Testes

- [x] Criar `tests/messaging/test_gchat.py`
  - Teste de herança MessageBus
  - Teste de `required_env_vars` e `env_template`
  - Teste de `default_chat_id` e `supports_threads`
  - Teste de `send_message` com mock do Google API client
  - Teste de `send_message` com thread_id
  - Teste de `send_approval_request` com Card v2
  - Teste de `_poll_loop` com mensagens mock
  - Teste de filtro de mensagens do bot (ignora eco)
  - Teste de `create_thread` retorna UUID string
  - Teste de registro no registry
