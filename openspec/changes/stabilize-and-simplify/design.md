## Context

O ai-squad evoluiu de POC para uso diário, mas acumula dívida técnica que causa instabilidade:

- **engine.py** (1044 LOC) concentra 6 responsabilidades distintas (prompt building, agent management, pipeline, state, messaging, knowledge)
- **daemon.py** (901 LOC) acessa 11+ atributos privados do engine, criando acoplamento frágil
- Estado mutável compartilhado (`_default_user_id`, `_default_demand_id`) causa race conditions
- Retry duplicado entre `claude_agent_sdk.py` e `agent_runner.py`
- 11 callbacks + 11 setters individuais = 77 linhas de boilerplate
- Timeout → hard fail → auto-recovery cascata → sistema para
- Progress armazenado internamente, nunca chega ao usuário
- Prompt agrega todo o contexto a cada chamada (consumo excessivo de tokens)

## Goals / Non-Goals

**Goals:**
- Sistema estável que não para em timeout e se recupera sozinho
- Mensagens do usuário sempre processadas (sem race condition)
- Visibilidade do que agentes estão fazendo (progress + logs + tokens)
- Código simples, sem boilerplate, seguindo SOLID/KISS/DRY
- Cobertura de testes >85%, zero issues pyright/pylance
- engine.py ≤600 LOC, daemon.py ≤550 LOC

**Non-Goals:**
- Multi-tenancy (múltiplos usuários simultâneos) — será endereçado futuramente
- Novo provider de IA — foco é estabilizar os existentes
- Mudanças na interface pública (CLI, config.yaml)
- Reescrever stores (journal, conversation, lessons) — já funcionam bem

## Decisions

### D1. Semáforo no Squad Lead (não fila)

**Decisão:** Usar `asyncio.Semaphore(1)` para serializar acesso ao Squad Lead, com mensagens enfileiradas implicitamente pelo asyncio event loop.

**Alternativas consideradas:**
- `asyncio.Queue` explícita → overhead desnecessário para single-user; semáforo resolve com menos código
- Lock + retry → risco de starvation se Squad Lead demora

**Rationale:** Para o cenário atual (single-user via TUI), o semáforo é suficiente. Quando multi-user for necessário, evoluir para Queue com isolamento por demand_id.

### D2. Estado como parâmetro, não instância

**Decisão:** `run_squad_lead(user_id, demand_id, thread_id)` recebe contexto como parâmetros. Eliminar `_default_user_id`, `_default_demand_id`, `_default_thread_id` como variáveis de instância.

**Alternativas consideradas:**
- Dataclass `RequestContext` → bom, mas adiciona abstração para 3 campos; inline é mais KISS
- Thread-local storage → complexidade desnecessária para asyncio

**Rationale:** Parâmetros explícitos eliminam race conditions e tornam o fluxo de dados rastreável.

### D3. Callback registry com dict

**Decisão:** Substituir 11 campos + 11 setters por `dict[str, Callable]` com `on(event, cb)` e `emit(event, *args)`.

**Alternativas consideradas:**
- EventEmitter class → over-engineering para uso interno
- Manter setters mas com `__setattr__` genérico → frágil

**Rationale:** Dict é o approach mais simples que funciona. Elimina 77 LOC de boilerplate. Type safety via constantes de evento.

### D4. MCP tools declarativos

**Decisão:** Definir tools como lista de dicts `[{name, callback_event, params, description}]` e gerar handlers via loop.

**Alternativas consideradas:**
- Code generation → complexidade de build
- Decorators customizados → ainda requer boilerplate por tool

**Rationale:** Data-driven elimina ~200 LOC de handlers repetitivos. Adicionar nova tool = adicionar 1 dict.

### D5. Retry compartilhado extraído

**Decisão:** Criar `ai_squad/common/retry.py` com função `retry_with_backoff()` usada por adapter e runner. Timeouts passam a ser retentáveis (com budget de tempo restante).

**Alternativas consideradas:**
- Decorator `@retryable` → menos flexível para async com budget de tempo
- Biblioteca externa (tenacity) → dependência extra para algo simples

**Rationale:** Uma função async de ~20 LOC resolve. Timeout retry usa tempo restante do budget original em vez de resetar o timer.

### D6. Split engine.py em 3 módulos

**Decisão:**
- `engine.py` (~400 LOC) — core: run_squad_lead, delegação, callbacks wiring
- `prompt_builder.py` — montagem de contexto otimizada (já existe, será expandido)
- `pipeline_handler.py` — callbacks de pipeline (advance/skip/rerun/get_state)

**Alternativas consideradas:**
- Split em 6 módulos (como spec core C7) → over-splitting para o tamanho atual; 3 é suficiente
- Manter monolítico e só extrair funções → não resolve o problema de coesão

**Rationale:** 3 módulos com responsabilidades claras. Pipeline handler é natural porque já é um conjunto coeso de 4 callbacks. Prompt builder já existe como módulo.

### D7. Daemon usa API pública do engine

**Decisão:** Engine expõe `get_status() -> EngineStatus` (dataclass com squad_lead_busy, running_agents, etc.). Daemon para de acessar `engine._private`.

**Alternativas consideradas:**
- Properties públicas individuais → muitas, sem coesão
- Manter acesso privado com "gentleman's agreement" → quebra com refactor

**Rationale:** DTO público é estável e testável. Daemon vira consumidor do engine, não inspetor.

### D8. Progress streaming periódico

**Decisão:** `_handle_progress()` acumula mensagens e a cada 15s envia as últimas 3 ao usuário via message bus, com prefixo do agente.

**Alternativas consideradas:**
- Enviar cada progress imediatamente → spam no Telegram
- Só melhorar /status → usuário precisa lembrar de consultar

**Rationale:** 15s é frequente o suficiente para dar visibilidade sem ser intrusivo. 3 mensagens dão contexto sem flood.

### D9. Logging estruturado com token tracking

**Decisão:**
- Logger `ai-squad.sdk` com handler de arquivo rotativo (`logs/agent.log`, 5MB, 3 backups)
- SDK stderr → logger.debug
- Cada chamada ao adapter loga: agent_name, input_tokens, output_tokens, duration_ms, model
- Token totals acumulados em memória, expostos via `/status`

**Alternativas consideradas:**
- Structured logging (JSON) → overhead de parsing para uso humano
- Métricas Prometheus → infra extra desnecessária

**Rationale:** Arquivo texto rotativo é simples e resolve o caso "quero ver o que o SDK fez". Token tracking em memória é leve e basta para exposição via TUI.

### D10. RunnerContext enxuto

**Decisão:** Reduzir de 13 campos para 5: `adapter`, `message_bus`, `workspace`, `agent_timeout`, `personas`. Stores acessados via engine quando necessário (injetados como callbacks).

**Alternativas consideradas:**
- Eliminar RunnerContext e passar tudo como parâmetro → muitos parâmetros por método
- Manter 13 campos → acoplamento desnecessário

**Rationale:** Runner precisa de 5 coisas. O resto é responsabilidade do engine e é acessado via callback quando o agente completa.

## Risks / Trade-offs

| Risco | Mitigação |
|-------|-----------|
| Refactor grande pode introduzir regressões | Cobertura >85% antes e depois; testes existentes (400+) como safety net |
| Semáforo pode causar latência se Squad Lead demora | Timeout no semáforo (30s) + feedback "aguardando Squad Lead..." |
| Callback registry perde type safety dos setters | Constantes tipadas para nomes de evento; testes unitários validam wiring |
| Split de engine pode quebrar integrações nos testes | Manter imports públicos no `__init__.py` do orchestrator |
| Token tracking em memória perde dados no restart | Aceitável — é métrica operacional, não dado de negócio |
| Timeout retry pode consumir mais tokens | Budget de tempo restante limita; circuit breaker previne loops |
