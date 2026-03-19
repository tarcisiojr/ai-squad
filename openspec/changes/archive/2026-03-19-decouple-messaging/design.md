# Design: decouple-messaging

## Visão Geral

Desacoplar o daemon do Telegram movendo responsabilidades provider-específicas para dentro de cada implementação de `MessageBus`, e usando `PlatformFactory` como ponto único de resolução.

## Mudanças na Interface

### MessageBus (src/messaging/interface.py)

Novos métodos abstratos:

```python
@abstractmethod
async def start(self) -> None:
    """Inicia o loop de recebimento de mensagens."""
    ...

@abstractmethod
async def stop(self) -> None:
    """Para o loop de recebimento gracefully."""
    ...

@classmethod
@abstractmethod
def required_env_vars(cls) -> list[str]:
    """Variáveis de ambiente necessárias para este provider."""
    ...

@classmethod
@abstractmethod
def env_template(cls) -> str:
    """Template de .env com placeholders para este provider."""
    ...
```

Nova propriedade:

```python
@property
def supports_threads(self) -> bool:
    """Se o provider suporta threads/tópicos. Default: False."""
    return False
```

### thread_id: int | None → str | None

Todas as assinaturas mudam. Providers convertem internamente:
- Telegram: `str(message_thread_id)` ↔ `int(thread_id)`
- Slack: usa thread_ts (já string)
- GChat: usa thread key (já string)
- Discord: `str(thread.id)` ↔ `int(thread_id)`

## Mudanças no Daemon

### Antes
```python
from src.messaging.telegram import TelegramMessageBus

self._bus: TelegramMessageBus | None = None
self._bus = TelegramMessageBus(token=..., ...)
await app.updater.start_polling()
```

### Depois
```python
from src.messaging.interface import MessageBus

self._bus: MessageBus | None = None
self._bus = factory.create_message_bus(config)
await self._bus.start()
```

### Responsabilidades movidas para o provider

| Responsabilidade | Antes (daemon) | Depois (provider) |
|-----------------|----------------|-------------------|
| Iniciar polling/websocket | `app.updater.start_polling()` | `bus.start()` |
| Parar polling | `app.updater.stop()` | `bus.stop()` |
| Detectar forum mode | `_detect_forum_mode()` | `bus.supports_threads` |
| Tokens necessários | hardcoded no daemon | `bus.required_env_vars()` |

## Mudanças no TelegramMessageBus

- Implementa `start()`: inicializa app + inicia polling
- Implementa `stop()`: para polling + shutdown app
- Implementa `required_env_vars()`: `["TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]`
- Implementa `env_template()`: template com placeholders
- `supports_threads` retorna `True` se chat é fórum (detecta em `start()`)
- Converte `thread_id` de `str` para `int` internamente
- Construtor recebe tokens via kwargs genéricos ou env vars direto

## Mudanças no CLIMessageBus

- Implementa `start()`: no-op ou inicia leitura stdin
- Implementa `stop()`: no-op
- Implementa `required_env_vars()`: `[]`
- Implementa `env_template()`: string vazia

## Factory e Registry

### PlatformFactory — registro de providers

```python
# src/messaging/registry.py
MESSAGING_PROVIDERS: dict[str, type[MessageBus]] = {}

def register(name: str, cls: type[MessageBus]) -> None:
    MESSAGING_PROVIDERS[name] = cls

def get(name: str) -> type[MessageBus]:
    if name not in MESSAGING_PROVIDERS:
        raise ValueError(f"Provider não registrado: '{name}'")
    return MESSAGING_PROVIDERS[name]
```

Cada provider se registra no import:
```python
# src/messaging/telegram.py
from src.messaging.registry import register
register("telegram", TelegramMessageBus)
```

### PlatformFactory.create_message_bus()

Usa registry para resolver. Passa env vars relevantes como kwargs.

## CLI Templates

### config.py

`ENV_TEMPLATE` dividido em:
- `COMMON_ENV_TEMPLATE` — tokens comuns (CLAUDE, GITHUB)
- Provider-específico vem de `cls.env_template()`

`REQUIRED_ENV_VARS` fica apenas com tokens comuns. Validação de tokens do provider delegada para `required_env_vars()`.

### team_manager.py

- `create()` aceita `--messaging` flag
- Gera `.env` combinando template comum + template do provider
- Default: "telegram" (backward compatible)

## Impacto em Testes

- Testes que mocam `TelegramMessageBus` continuam funcionando
- Testes do daemon precisam ajustar para usar factory/mock
- Novos testes para registry e validação dinâmica de tokens
- thread_id nos mocks muda de `int` para `str`

## Decisões

1. **Registry em módulo separado** (não dentro da factory) — evita imports circulares
2. **Auto-registro no import** — simples, sem metaclasses
3. **thread_id como str** — máximo de compatibilidade entre providers
4. **Provider lê env vars direto** — não precisa passar via construtor (mais simples)
5. **Backward compatible** — default "telegram" em todo lugar
