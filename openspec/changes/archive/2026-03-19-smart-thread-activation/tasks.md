## Tasks

### 1. Configuração activation_mode
- [x] Adicionar campo `activation_mode` (mention/all/command) ao parsing de config.yaml em `src/factory.py`
- [x] Definir default `mention` quando não configurado
- [x] Validar valor na inicialização (erro claro se inválido)

### 2. Interface MessageBus — novos métodos
- [x] Adicionar método `is_mention(message_data) → bool` na interface `MessageBus`
- [x] Adicionar método `is_dm(message_data) → bool` na interface `MessageBus`
- [x] Adicionar propriedade `bot_identifier → str` (username do bot para detecção)

### 3. Filtro de ativação no Telegram
- [x] Implementar `is_mention()` no TelegramMessageBus — verifica `entities` tipo `mention` com `@bot_username`
- [x] Implementar `is_dm()` no TelegramMessageBus — verifica tipo do chat (private vs group/supergroup)
- [x] Aplicar filtro no handler `_handle_text`: ignorar se grupo + sem menção/comando (conforme activation_mode)
- [x] Garantir que pending_reply ignora o filtro (sempre captura resposta)

### 4. Filtro de ativação no GChat
- [x] Implementar `is_mention()` no GChatMessageBus — verifica annotations com userMention tipo BOT
- [x] Implementar `is_dm()` no GChatMessageBus — verifica se é DM ou espaço
- [x] Aplicar filtro no polling de mensagens: ignorar se espaço + sem menção (conforme activation_mode)
- [x] Garantir que pending_reply ignora o filtro

### 5. ThreadTracker — componente core
- [x] Criar `src/orchestrator/thread_tracker.py` com classe `ThreadTracker`
- [x] Implementar estados: INACTIVE, ACTIVE, STANDBY com enum
- [x] Implementar `on_message(thread_id, is_bot, is_mention) → ThreadAction` que retorna: PROCESS, IGNORE ou HANDOFF
- [x] Implementar transição ACTIVE → STANDBY quando humano responde sem menção
- [x] Implementar transição STANDBY → ACTIVE quando @mention chega
- [x] Implementar transição INACTIVE → ACTIVE quando primeira @mention chega

### 6. ThreadTracker — persistência
- [x] Implementar `save()` que grava `state/threads.json` via `write_json_atomic`
- [x] Implementar `load(state_dir)` que carrega estado no startup
- [x] Implementar limpeza de threads com última atividade > `inactive_thread_ttl`
- [x] Salvar estado após cada transição

### 7. ThreadTracker — timeouts
- [x] Implementar check periódico de `standby_timeout` (asyncio task)
- [x] Quando timeout atingido, enviar mensagem de oferta de ajuda via MessageBus
- [x] Carregar tempos do config.yaml (standby_timeout, inactive_thread_ttl, handoff_message)
- [x] Usar defaults sensatos: standby_timeout=1800, inactive_thread_ttl=86400, handoff_message=true

### 8. Integração com Daemon
- [x] Injetar ThreadTracker no daemon via factory
- [x] No `_message_callback`, consultar ThreadTracker antes de processar
- [x] Enviar mensagem de handoff quando ThreadTracker retorna HANDOFF
- [x] Passar activation_mode para os providers de messaging na inicialização

### 9. Testes
- [x] Testes unitários para ThreadTracker: transições de estado (INACTIVE→ACTIVE→STANDBY→ACTIVE)
- [x] Testes unitários para ThreadTracker: persistência (save/load)
- [x] Testes unitários para ThreadTracker: limpeza por TTL
- [x] Testes unitários para ThreadTracker: timeout de standby
- [x] Testes unitários para filtro de menção no Telegram (mock de entities)
- [x] Testes unitários para filtro de menção no GChat (mock de annotations)
- [x] Testes de integração: mensagem em grupo sem menção é ignorada
- [x] Testes de integração: pending_reply ignora activation_mode
