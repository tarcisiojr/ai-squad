# Proposal: decouple-messaging

## Problema

O daemon e a CLI estão fortemente acoplados ao Telegram:

- `daemon.py` importa `TelegramMessageBus` diretamente, instancia com tokens hardcoded, e usa APIs específicas do Telegram (Forum Topics, polling)
- `factory.py` valida `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID` como obrigatórios independente do provider
- `cli/templates/config.py` gera `.env` com tokens Telegram hardcoded
- `thread_id` é `int | None` (tipo Telegram), mas Slack usa `str` (timestamp) e GChat usa `str` (space path)

Isso impede adicionar novos providers (GChat, Discord, Slack) sem duplicar lógica do daemon.

## Solução

Desacoplar o sistema de mensageria via factory pattern, tornando o daemon agnóstico ao provider:

1. **Expandir `MessageBus`** com métodos de ciclo de vida (`start/stop`) e auto-descrição (`required_env_vars/env_template`)
2. **Generalizar `thread_id`** de `int | None` para `str | None`
3. **Daemon genérico** — usa `MessageBus` (ABC) via factory, sem imports diretos de providers
4. **CLI dinâmica** — gera `.env` e valida tokens baseado no `messaging_provider` escolhido

## Escopo

### Incluso
- Refatorar `MessageBus` interface
- Refatorar `daemon.py` para usar factory
- Refatorar `TelegramMessageBus` para implementar novos métodos
- Refatorar `CLIMessageBus` para implementar novos métodos
- Refatorar `cli/templates/config.py` para templates dinâmicos
- Refatorar `factory.py` — validação de tokens por provider
- Ajustar tipo `thread_id` em toda a codebase
- Ajustar testes existentes

### Excluído
- Implementação de novos providers (GChat, Discord, Slack) — change separada
- Voice/transcrição — fica no provider que suportar
- Mudanças no pipeline ou engine

## Motivação

Preparar a plataforma para suportar GChat (prioridade — IM da empresa do usuário), Discord e Slack como providers de mensageria alternativos ao Telegram.
