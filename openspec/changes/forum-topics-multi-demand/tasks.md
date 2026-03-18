## 1. MessageContext e Interface do Bus

- [x] 1.1 Criar dataclass `MessageContext(chat_id, user_id, thread_id, demand_id)` em `src/messaging/context.py`
- [x] 1.2 Adicionar parâmetro `thread_id: int | None = None` (keyword-only) em `send_message`, `send_approval_request`, `ask_user`, `notify`, `send_photo`, `send_typing` na interface `MessageBus`
- [x] 1.3 Adicionar método abstrato `create_thread(chat_id: str, title: str) -> int | None` na interface `MessageBus`
- [x] 1.4 Atualizar `CLIMessageBus` — aceitar e ignorar `thread_id` em todos os métodos, `create_thread` retorna None

## 2. TelegramMessageBus — Suporte a Forum Topics

- [x] 2.1 Atualizar `_handle_text` para extrair `message_thread_id` e `from_user.id` do update e propagar via callback (assinatura do callback muda para incluir thread_id e user_id)
- [x] 2.2 Atualizar `_handle_voice` e `_handle_photo` para extrair e propagar `message_thread_id` e `from_user.id`
- [x] 2.3 Atualizar `_send` para aceitar e propagar `message_thread_id` para `bot.send_message`
- [x] 2.4 Atualizar `send_message`, `send_approval_request`, `ask_user`, `notify`, `send_photo`, `send_typing` para aceitar e propagar `thread_id`
- [x] 2.5 Implementar `create_thread` chamando `bot.create_forum_topic(chat_id, name)` e retornando `message_thread_id`

## 3. Mapeamento thread_id ↔ demand_id

- [x] 3.1 Criar classe `ThreadDemandMap` em `src/orchestrator/thread_map.py` com métodos `add(thread_id, demand_id)`, `get_demand(thread_id)`, `get_thread(demand_id)`, `load()`, `save()`
- [x] 3.2 Persistir mapeamento em `state/thread-demands.json` usando `atomic_write`
- [x] 3.3 Carregar mapeamento na inicialização do daemon (`_setup_components`)

## 4. Roteamento no Daemon

- [x] 4.1 Atualizar callback de `_handle_new_demand` para receber `thread_id` e `user_id` além de `text`
- [x] 4.2 Implementar lógica de roteamento: se `thread_id` está no mapeamento → usar demand_id correspondente; se thread_id=None ou Geral → Squad Lead sessão geral
- [x] 4.3 Detectar modo fórum via `chat.type == "supergroup"` e cache de `is_forum` na inicialização
- [x] 4.4 Na criação de demanda pelo Squad Lead (via `start_agent`): gerar demand_id, criar tópico via `bus.create_thread`, persistir mapeamento, enviar mensagem inicial no tópico
- [x] 4.5 Separar `chat_id` (grupo) de `user_id` (from_user.id) em todos os handlers — não usar `chat_id` como `user_id`

## 5. Propagação de thread_id no Engine

- [x] 5.1 Adicionar campo `thread_id: int | None = None` em `RunningAgent` (tools.py)
- [x] 5.2 No `engine.run_squad_lead`, aceitar e propagar `thread_id` para callbacks de envio de mensagem
- [x] 5.3 Nos callbacks `_send_message_callback`, `_send_image_callback`, `_report_progress_callback` — resolver `thread_id` a partir do demand_id do agente via `ThreadDemandMap`
- [x] 5.4 Atualizar `prompt_builder.get_running_agents_status` para agrupar agentes por demand_id e mostrar demand_id no status

## 6. Testes

- [x] 6.1 Testes unitários para `ThreadDemandMap` — add, get, persistência, load após restart
- [x] 6.2 Testes unitários para `MessageContext` — criação, valores default
- [x] 6.3 Testes para roteamento no daemon — mensagem em tópico mapeado, tópico geral, tópico desconhecido, DM
- [x] 6.4 Testes para `TelegramMessageBus` — propagação de thread_id em send_message, create_thread
- [x] 6.5 Testes para engine — thread_id propagado nos callbacks, RunningAgent com thread_id
- [x] 6.6 Testes para fallback modo flat — DM sem thread_id preserva comportamento atual
