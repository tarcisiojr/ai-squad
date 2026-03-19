# Tasks: decouple-messaging

## Fase 1: Interface e Registry

- [x] Expandir `MessageBus` em `src/messaging/interface.py`
  - Adicionar métodos abstratos: `start()`, `stop()`, `required_env_vars()`, `env_template()`
  - Adicionar propriedade `supports_threads` (default False)
  - Mudar `thread_id: int | None` → `str | None` em todos os métodos
  - Mudar retorno de `create_thread()` de `int | None` para `str | None`

- [x] Criar `src/messaging/registry.py`
  - Dict `MESSAGING_PROVIDERS: dict[str, type[MessageBus]]`
  - Funções `register(name, cls)` e `get(name)`

## Fase 2: Refatorar Providers Existentes

- [x] Refatorar `TelegramMessageBus` em `src/messaging/telegram.py`
  - Implementar `start()`: `_ensure_app()` + `app.initialize()` + `app.start()` + `app.updater.start_polling()`
  - Implementar `stop()`: `updater.stop()` + `app.stop()` + `app.shutdown()`
  - Implementar `required_env_vars()`: `["TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]`
  - Implementar `env_template()`: template com placeholders Telegram
  - Implementar `supports_threads`: detectar forum mode em `start()`
  - Converter `thread_id` str↔int internamente em todos os métodos
  - Registrar no registry: `register("telegram", TelegramMessageBus)`

- [x] Refatorar `CLIMessageBus` em `src/messaging/cli.py`
  - Implementar `start()`, `stop()`: no-op
  - Implementar `required_env_vars()`: `[]`
  - Implementar `env_template()`: string vazia
  - Converter `thread_id` para str nos métodos que usam
  - Registrar no registry: `register("cli", CLIMessageBus)`

## Fase 3: Refatorar Daemon

- [x] Refatorar `src/daemon.py`
  - Remover import de `TelegramMessageBus`
  - Tipar `self._bus` como `MessageBus | None`
  - Usar registry para instanciar provider
  - Substituir `app.updater.start_polling()` por `bus.start()`
  - Substituir shutdown do app por `bus.stop()`
  - Remover `_detect_forum_mode()` — usar `bus.supports_threads`
  - Ajustar `_create_demand_topic()` para usar `str` thread_id
  - Ajustar `_handle_new_demand()` para `str` thread_id
  - Provider lê seus tokens do env (daemon não passa explicitamente)

## Fase 4: Refatorar Factory e CLI

- [x] Refatorar `src/factory.py`
  - `validate_required_tokens()` consulta provider via registry para tokens específicos
  - Tokens comuns (CLAUDE, GITHUB) ficam hardcoded
  - Tokens do provider vêm de `required_env_vars()`

- [x] Refatorar `src/cli/templates/config.py`
  - Separar `ENV_TEMPLATE` em `COMMON_ENV_TEMPLATE` + provider-específico
  - `REQUIRED_ENV_VARS` fica apenas com tokens comuns
  - Função `get_env_template(provider: str)` combina comum + provider

- [x] Refatorar `src/cli/team_manager.py`
  - Aceitar parâmetro `--messaging` em `create()`
  - Gerar `.env` com template dinâmico baseado no provider
  - Default: "telegram"

- [x] Refatorar `src/cli/main.py`
  - Adicionar opção `--messaging` ao comando `create`

## Fase 5: Ajustar thread_id na Codebase

- [x] Ajustar `src/orchestrator/engine.py` — thread_id int→str
- [x] Ajustar `src/orchestrator/thread_map.py` — thread_id int→str
- [x] Ajustar `src/messaging/context.py` — se usar thread_id

## Fase 6: Testes

- [x] Ajustar `tests/messaging/test_telegram.py` — thread_id str, novos métodos
- [x] Ajustar `tests/test_daemon.py` — factory mock, MessageBus genérico
- [x] Ajustar `tests/test_daemon_extended.py` — idem
- [x] Ajustar `tests/test_factory.py` — validação dinâmica de tokens
- [x] Ajustar `tests/test_integration.py` — thread_id str
- [x] Ajustar `tests/cli/test_team_manager.py` — --messaging flag
- [x] Criar `tests/messaging/test_registry.py` — registro e resolução de providers
