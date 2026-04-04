## Why

O ai-squad saiu do estágio de POC mas carrega dívida técnica que compromete a usabilidade e a manutenção. Problemas concretos reportados pelo usuário:

1. **Squad Lead não responde mensagens novas** — race condition com estado mutável compartilhado sobrescreve contexto entre requisições concorrentes
2. **Sistema para em timeout e não volta** — timeouts não são retentados; auto-recovery cascateia falhas ao re-chamar o Squad Lead (que também pode dar timeout)
3. **Sem visibilidade do que o agente faz** — progress callbacks armazenam internamente mas nunca chegam ao usuário; feedback genérico "Trabalhando..." sem detalhe
4. **Consumo excessivo de tokens** — `_build_squad_lead_prompt()` (475 LOC) agrega todo o contexto a cada chamada; race conditions e retries multiplicam o custo
5. **Código complexo e desorganizado** — engine.py (1044 LOC), daemon.py (901 LOC), callbacks boilerplate, retry duplicado, estado em 3 lugares, acoplamento via `_private` attrs

## What Changes

- **Fila de mensagens e semáforo** para serializar acesso ao Squad Lead (elimina race condition)
- **Estado como parâmetro** em vez de variáveis de instância mutáveis (`_default_user_id`, `_default_demand_id`, `_default_thread_id` → parâmetros de `run_squad_lead()`)
- **Retry com backoff para timeouts** + circuit breaker para evitar cascata de falhas
- **Progress streaming** — últimas mensagens de progresso enviadas ao usuário periodicamente
- **Logging estruturado** — SDK stdout/stderr → arquivo rotativo; input/output tokens logados por chamada
- **Callback registry** — substituir 11 campos + 11 setters por dict com `on(event, callback)`
- **MCP tools declarativos** — definição data-driven em vez de N handlers individuais
- **Retry compartilhado** — extrair utility único usado por adapter e runner
- **Split engine.py** — separar em orchestrator core, prompt builder, pipeline handler
- **Split daemon.py** — separar lifecycle de message routing; eliminar acesso a `_private` attrs do engine
- **RunnerContext enxuto** — de 13 campos para ~5 essenciais
- **Remover código morto** — preset `personal-assistant`, passthrough methods, flags hardcoded, `return` inalcançável
- **Prompt otimizado** — contexto incremental, cache de partes estáticas, model routing efetivo

## Capabilities

### New Capabilities
- `message-queue`: Fila async + semáforo para serializar acesso ao Squad Lead e evitar race conditions
- `error-recovery`: Retry com backoff para timeouts, circuit breaker, recuperação automática sem intervenção do usuário
- `observability`: Logging estruturado (arquivo rotativo), token tracking por chamada, progress streaming ao usuário
- `callback-registry`: Sistema de eventos com registry dict substituindo callbacks individuais
- `declarative-tools`: Registro de MCP tools via definição declarativa (data-driven)
- `shared-retry`: Utility de retry com backoff compartilhado entre adapter e runner

### Modified Capabilities
- `orchestrator`: Refactor — split engine.py em módulos menores; estado como parâmetro; prompt builder otimizado
- `core`: Refactor — split daemon.py; eliminar acesso a attrs privados do engine; RunnerContext enxuto

## Impact

- **Arquivos principais**: `engine.py`, `daemon.py`, `agent_runner.py`, `claude_agent_sdk.py`, `prompt_builder.py`
- **Novos módulos**: `message_queue.py`, `token_tracker.py`, `retry.py`, `callback_registry.py`
- **Remoção**: `presets/personal-assistant/`, passthrough methods, `FEEDBACK_TIME_ONLY`
- **Testes**: cobertura exigida >85%, zero issues pyright/pylance
- **Breaking changes**: nenhum na interface pública (CLI, config.yaml). Mudanças internas nos módulos do orchestrator
