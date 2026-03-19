# Spec: Daemon Desacoplado

## Requisitos

### REQ-1: Daemon agnóstico ao provider
- Daemon importa apenas `MessageBus` (ABC), nunca implementações concretas
- Instanciação via `PlatformFactory.create_message_bus()`
- Tipagem interna usa `MessageBus`, não `TelegramMessageBus`

### REQ-2: Ciclo de vida delegado ao provider
- `daemon.run()` chama `bus.start()` em vez de `app.updater.start_polling()`
- `daemon._shutdown()` chama `bus.stop()` em vez de `app.updater.stop()`
- Cada provider encapsula seu loop interno

### REQ-3: Forum mode delegado ao provider
- `_detect_forum_mode()` removido do daemon
- Provider expõe `supports_threads: bool` (propriedade ou método)
- Daemon consulta provider para decidir se cria threads

### REQ-4: Registro automático de providers
- Providers registrados na factory automaticamente (registry pattern)
- Mapeamento: nome string → classe concreta
- Nomes: "telegram", "cli", "discord", "slack", "gchat"

## Cenários

### Cenário 1: Boot com Telegram
- Dado config.yaml com `messaging_provider: telegram`
- E `.env` com `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID`
- Quando daemon inicia
- Então factory resolve TelegramMessageBus
- E `bus.start()` inicia polling do Telegram
- E daemon opera normalmente

### Cenário 2: Boot com CLI
- Dado config.yaml com `messaging_provider: cli`
- Quando daemon inicia
- Então factory resolve CLIMessageBus
- E `bus.start()` inicia leitura de stdin

### Cenário 3: Shutdown graceful
- Dado daemon rodando com qualquer provider
- Quando recebe SIGTERM
- Então chama `bus.stop()`
- E provider encerra seu loop
