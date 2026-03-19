# Spec: MessageBus Interface Expandida

## Requisitos

### REQ-1: Ciclo de vida do provider
- `MessageBus` deve ter método abstrato `start()` para iniciar o loop de recebimento
- `MessageBus` deve ter método abstrato `stop()` para encerrar gracefully
- Cada provider implementa seu mecanismo (polling, websocket, pub/sub)

### REQ-2: Auto-descrição de configuração
- `MessageBus` deve ter classmethod `required_env_vars()` retornando lista de variáveis necessárias
- `MessageBus` deve ter classmethod `env_template()` retornando template de `.env` para o provider
- Usado pela CLI para gerar `.env` e pela factory para validar tokens

### REQ-3: thread_id genérico
- Tipo de `thread_id` muda de `int | None` para `str | None` em toda a interface
- Providers convertem internamente (Telegram: `str(int)`, Slack: timestamp string, GChat: thread key)
- `create_thread()` retorna `str | None` em vez de `int | None`

### REQ-4: Detecção de capacidades movida para provider
- `_detect_forum_mode()` sai do daemon e vai para o provider (método `supports_threads()` ou similar)
- Provider sabe se suporta threads, voice, fotos, documentos, reações

## Cenários

### Cenário 1: Telegram continua funcionando
- Dado que `messaging_provider: telegram` no config.yaml
- Quando o daemon inicia
- Então TelegramMessageBus é instanciado via factory
- E polling do Telegram funciona como antes
- E Forum Topics continuam funcionando

### Cenário 2: Provider inexistente
- Dado que `messaging_provider: whatsapp` no config.yaml
- Quando o daemon tenta iniciar
- Então erro claro: "Provider de mensageria não registrado: 'whatsapp'"

### Cenário 3: Tokens ausentes
- Dado que `messaging_provider: telegram` mas `TELEGRAM_TOKEN` ausente
- Quando o daemon valida tokens
- Então erro lista tokens faltantes do provider Telegram especificamente
