## MODIFIED Requirements

### Requirement: Telegram como provider padrão
O TelegramMessageBus SHALL ser o provider padrão de mensageria quando executando em modo daemon/Docker.

#### Scenario: Provider padrão em daemon mode
- **WHEN** o daemon inicia sem `messaging_provider` explícito no config
- **THEN** MUST usar TelegramMessageBus como provider padrão

#### Scenario: Bot token por time
- **WHEN** o time é configurado com TELEGRAM_TOKEN no .env
- **THEN** MUST usar esse token para criar o bot exclusivo desse time

#### Scenario: Chat ID configurável
- **WHEN** TELEGRAM_CHAT_ID está definido no .env
- **THEN** MUST enviar todas as notificações e pedidos de aprovação para esse chat

## ADDED Requirements

### Requirement: Recebimento de demandas via Telegram
O TelegramMessageBus SHALL suportar recebimento de novas demandas via mensagens de texto.

#### Scenario: Nova demanda por texto
- **WHEN** o usuário envia uma mensagem de texto no chat configurado
- **THEN** o bus MUST encaminhar o texto como nova demanda ao daemon

#### Scenario: Nova demanda por voz
- **WHEN** o usuário envia mensagem de voz no chat configurado e OPENAI_API_KEY está configurada
- **THEN** o bus MUST transcrever o áudio via Whisper e encaminhar como nova demanda

### Requirement: Polling mode para Telegram
O TelegramMessageBus SHALL usar polling mode (não webhook) para simplificar deploy em Docker.

#### Scenario: Polling ativo
- **WHEN** o daemon inicia com provider Telegram
- **THEN** MUST iniciar polling via `application.run_polling()` sem necessidade de URL pública ou certificado SSL
