# Spec: GChat Provider

## Requisitos

### REQ-1: Autenticação via Service Account
- Usa `google.oauth2.service_account.Credentials` com escopo `https://www.googleapis.com/auth/chat.bot`
- Credenciais lidas de arquivo JSON apontado por `GCHAT_CREDENTIALS_PATH`
- Space ID configurado via `GCHAT_SPACE_ID`

### REQ-2: Envio de mensagens
- `send_message()` envia texto via `spaces.messages.create()`
- Suporta `thread_id` como `threadKey` para responder em threads
- Prefixo com persona (avatar + nome) como no Telegram
- Mensagens longas (>4096 chars) são divididas em partes

### REQ-3: Recebimento via polling
- `start()` inicia loop assíncrono que faz `spaces.messages.list()` periodicamente
- Intervalo configurável (default: 3 segundos)
- Filtra mensagens do próprio bot (ignora eco)
- Detecta mensagens novas comparando com último timestamp visto
- `stop()` encerra o loop

### REQ-4: Aprovações via Cards v2
- `send_approval_request()` envia Card v2 com botões
- Cada opção é um botão com `onClick.action`
- Bot aguarda resposta via polling de interações (CARD_CLICKED)
- Timeout configurável

### REQ-5: Threads em Spaces
- `supports_threads` retorna True
- `create_thread()` retorna threadKey gerado (UUID)
- Mensagens em thread usam `thread.threadKey` + `messageReplyOption: REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD`

### REQ-6: Auto-descrição
- `required_env_vars()`: `["GCHAT_CREDENTIALS_PATH", "GCHAT_SPACE_ID"]`
- `env_template()`: template com placeholders
- `default_chat_id`: retorna `GCHAT_SPACE_ID`

## Cenários

### Cenário 1: Bot envia mensagem em Space
- Dado `GCHAT_SPACE_ID` configurado
- Quando `send_message("spaces/XXX", "Olá!")` é chamado
- Então mensagem aparece no Space do Google Chat

### Cenário 2: Bot recebe mensagem do usuário
- Dado polling ativo
- Quando usuário envia "Criar API" no Space
- Então callback `_message_callback` é chamado com texto, thread_id e user_id

### Cenário 3: Aprovação com Cards
- Dado `send_approval_request()` chamado com opções ["Aprovar", "Rejeitar"]
- Quando Card v2 é enviado com 2 botões
- E usuário clica em "Aprovar"
- Então retorna "Aprovar"

### Cenário 4: Mensagem em thread
- Dado thread existente com threadKey "abc-123"
- Quando `send_message(space, "msg", thread_id="abc-123")`
- Então mensagem aparece na thread correta
