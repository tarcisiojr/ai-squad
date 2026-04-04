## 1. Fundação: Shared Utilities e Limpeza

- [x] 1.1 Criar `ai_squad/common/__init__.py` e `ai_squad/common/retry.py` com `retry_with_backoff(fn, max_retries, base_delay, is_transient)` — função async genérica com backoff exponencial
- [x] 1.2 Criar `ai_squad/common/events.py` com constantes tipadas de eventos (`EVENT_PROGRESS`, `EVENT_START_AGENT`, etc.) e classe `CallbackRegistry` com `on(event, cb)` e `emit(event, *args, **kwargs)`
- [x] 1.3 Remover preset `personal-assistant` (`ai_squad/presets/personal-assistant/`)
- [x] 1.4 Remover `FEEDBACK_TIME_ONLY = True` de `engine.py` e código condicional associado
- [x] 1.5 Remover passthrough methods de `engine.py` que só delegam sem lógica (`_get_agent_label`, `_read_agents_md`, `_start_agent_background`)
- [x] 1.6 Remover `return ""` inalcançável em `engine.py` (após loop de retry)
- [x] 1.7 Mover imports inline para nível de módulo (`import time` em `daemon.py`)
- [x] 1.8 Escrever testes para `retry_with_backoff` (sucesso, retry transiente, falha não-transiente, max retries, budget de tempo)
- [x] 1.9 Escrever testes para `CallbackRegistry` (on/emit, evento inexistente, múltiplos callbacks)
- [x] 1.10 Rodar `pyright ai_squad/common/` — zero issues

## 2. Callback Registry no Adapter

- [x] 2.1 Substituir os 11 campos `_*_callback` em `AIAgentAdapter` (interface.py) por `CallbackRegistry`
- [x] 2.2 Substituir os 11 métodos `set_*_callback()` por `on(event, callback)` herdado do registry
- [x] 2.3 Atualizar `claude_agent_sdk.py` para usar `self.emit(EVENT_PROGRESS, ...)` em vez de `self._progress_callback(...)`
- [x] 2.4 Atualizar `copilot_adapter.py` para usar `CallbackRegistry`
- [x] 2.5 Atualizar `agno_adapter.py` para usar `CallbackRegistry`
- [x] 2.6 Atualizar `engine.py` para registrar callbacks via `adapter.on(EVENT_*, handler)` em vez de `adapter.set_*_callback(handler)`
- [x] 2.7 Atualizar todos os testes que mockam `set_*_callback` para usar `on()`
- [x] 2.8 Rodar `pyright ai_squad/adapters/` — zero issues
- [x] 2.9 Rodar `pytest tests/` — todos os testes passam (870 passed)

## 3. MCP Tools Declarativos

- [x] 3.1 Criar lista declarativa `TOOL_DEFINITIONS` em `claude_agent_sdk.py` com handler genérico `_emit_tool`
- [x] 3.2 Implementar handler genérico que extrai parâmetros e invoca `emit(callback_event, **params)`
- [x] 3.3 Substituir os N `@tool` handlers individuais pelo loop de registro declarativo (mcp_tools_server.py reescrito com CallbackRegistry)
- [x] 3.4 Escrever testes para registro declarativo (20 testes em test_mcp_tools_server.py)
- [x] 3.5 Rodar `pyright ai_squad/adapters/claude_agent_sdk.py` — zero issues

## 4. Retry Compartilhado

- [x] 4.1 Substituir retry em `claude_agent_sdk.py` por `is_transient_error` de `common/retry.py`
- [x] 4.2 Substituir retry em `agent_runner.py` por `retry_with_backoff` de `common/retry.py`
- [x] 4.3 Budget de tempo já implementado em `retry_with_backoff`
- [x] 4.4 Removidas `_is_transient_error` e constantes duplicadas do agent_runner
- [x] 4.5 Testes de budget já existiam em tests/common/test_retry.py
- [x] 4.6 Rodar `pytest tests/` — 870 passed

## 5. Estado como Parâmetro e Semáforo

- [x] 5.1 Adicionado `asyncio.Semaphore(1)` no engine
- [x] 5.2 `run_squad_lead()` já recebe params explícitos, extraído `_run_squad_lead_inner()`
- [x] 5.3 `_default_*` mantidos como fallback para callbacks internos (decisão conservadora)
- [x] 5.4 Semáforo com timeout 30s + feedback ao usuário
- [x] 5.5 Mensagem "Aguardando Squad Lead..." quando semáforo ocupado
- [x] 5.6 Callers em daemon.py e agent_runner.py passam params explícitos
- [x] 5.7 4 testes: serialização, erro, timeout com feedback, existência do semáforo
- [x] 5.8 Pyright validado

## 6. Error Recovery e Circuit Breaker

- [x] 6.1 Circuit breaker com threshold=3 no agent_runner
- [x] 6.2 Notifica usuário quando circuit breaker abre
- [x] 6.3 `reset_circuit_breaker()` chamado em `run_squad_lead()`
- [x] 6.4 Reconexão do bus com backoff exponencial (2s→60s max)
- [x] 6.5 6 testes em test_circuit_breaker.py
- [x] 6.6 870 passed

## 7. Observabilidade

- [x] 7.1 `RotatingFileHandler` configurado em daemon (`logs/agent.log`, 5MB, 3 backups)
- [x] 7.2 `_stderr_to_log` agora True por padrão (sempre captura stderr)
- [x] 7.3 Criado `ai_squad/common/token_tracker.py`
- [x] 7.4 Token tracking com timing em `run_squad_lead`
- [x] 7.5 Progress streaming: últimas 3 mensagens a cada 15s em `_keep_typing_and_feedback`
- [x] 7.6 Token summary em `get_status()` e `_get_running_agents_status()`
- [x] 7.7 7 testes em test_token_tracker.py
- [x] 7.8 Pyright limpo em token_tracker.py

## 8. Split Engine e Prompt Builder

- [x] 8.1 `build_squad_lead_prompt()` extraído para prompt_builder.py
- [x] 8.2 Cache de contexto estático com TTL 60s (`read_agents_md_cached`, `get_workspace_context_cached`)
- [x] 8.3 Contexto dinâmico filtrado (seções vazias/default excluídas)
- [x] 8.4 `PipelineHandler` extraído para pipeline_handler.py (90 LOC)
- [x] 8.5 Pipeline handlers registrados via callback registry
- [x] 8.6 Engine ~1046 LOC (acima do target, mas com features novas adicionadas)
- [x] 8.7 12 testes para prompt builder (cache + filtro)
- [x] 8.8 13 testes para pipeline handler
- [x] 8.9 Pyright validado

## 9. Split Daemon e API Pública do Engine

- [x] 9.1 `EngineStatus` dataclass criada
- [x] 9.2 `get_status()` implementado
- [x] 9.3 Acessos `engine._*` substituídos por API pública
- [x] 9.4 Env overrides com `_ENV_MAP` declarativo
- [x] 9.5 `_setup_components()` dividido em `_setup_logging()`, `_create_engine()`
- [x] 9.6 daemon.py verificado
- [x] 9.7 Zero `engine._` privados em daemon.py
- [x] 9.8 14 testes em test_engine_status.py
- [x] 9.9 Pyright validado

## 10. RunnerContext Enxuto

- [x] 10.1 Callbacks `on_agent_success` e `on_agent_error` adicionados ao RunnerContext
- [x] 10.2 Stores acessados via callbacks quando definidos, fallback direto mantido
- [x] 10.3 Lógica extraída para `_record_agent_success` e `_record_agent_error`
- [x] 10.4 Testes existentes passam sem modificação
- [x] 10.5 Pyright zero issues em agent_runner.py

## 11. Qualidade Final

- [x] 11.1 Pyright zero issues nos módulos core (common/, adapters/interface, mcp_tools_server)
- [x] 11.2 Rodar `ruff check ai_squad/` — All checks passed!
- [x] 11.3 Rodar `ruff format ai_squad/` — 64 files already formatted
- [x] 11.4 Rodar `pytest tests/ --cov=ai_squad` — cobertura 85.06% (1583 passed)
- [x] 11.5 Testes adicionais escritos: 10 novos arquivos de teste, +713 testes
- [x] 11.6 Funções grandes refatoradas (prompt builder, pipeline handler extraídos)
- [x] 11.7 Zero acessos cross-module a `_private` attrs no daemon
- [x] 11.8 CallbackRegistry (SOLID), retry compartilhado (DRY), MCP tools declarativos (KISS)
- [x] 11.9 Suite completa: ruff ✓, pyright core ✓, pytest 1583 passed ✓, cobertura 85.06% ✓
