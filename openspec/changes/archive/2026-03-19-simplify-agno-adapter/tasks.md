## Tasks

### Task 1: Substituir _resolve_model por _normalize_model_id
- [x] Criar função `_normalize_model_id(model_id: str) -> str` que adiciona prefixo `provider:` se não presente
- [x] Remover função `_resolve_model()` e todos os imports condicionais de `agno.models.*`
- [x] Atualizar `_execute_agno` para passar `model=_normalize_model_id(model_id)` como string ao Agent
- [x] Atualizar testes: remover `TestResolveModel`, adicionar `TestNormalizeModelId`

**Arquivos**: `src/adapters/agno_adapter.py` (MODIFY), `tests/adapters/test_agno_adapter.py` (MODIFY)

### Task 2: Trocar asyncio.to_thread por agent.arun
- [x] Substituir `await asyncio.to_thread(agent.run, prompt)` por `await agent.arun(prompt)`
- [x] Remover import `RunResponse` (resposta de arun tem mesma interface)
- [x] Atualizar mock nos testes para usar `arun` em vez de `run`

**Arquivos**: `src/adapters/agno_adapter.py` (MODIFY), `tests/adapters/test_agno_adapter.py` (MODIFY)

### Task 3: Implementar cache de agentes
- [x] Adicionar `self._agents_cache: dict[str, tuple[Any, str]] = {}` no `__init__`
- [x] Criar método `_get_or_create_agent(agent_name, model_id, skills, instruction, tools) -> Agent`
- [x] Se cache hit e mesmo model_id → retorna cacheado
- [x] Se model_override (temporário) → cria novo sem cachear
- [x] Se cache miss → cria, cacheia, retorna
- [x] Adicionar método `clear_agent_cache()` para invalidação manual
- [x] Atualizar `_execute_agno` para usar `_get_or_create_agent`
- [x] Testes: cache hit, cache miss, model override não cacheia, clear_cache

**Arquivos**: `src/adapters/agno_adapter.py` (MODIFY), `tests/adapters/test_agno_adapter.py` (MODIFY)

### Task 4: Sessions nativas com SqliteDb
- [x] Adicionar parâmetro `state_dir: str = ""` no `__init__`
- [x] Criar `self._db = SqliteDb(db_file=f"{state_dir}/agno_sessions.db")` se state_dir fornecido
- [x] Remover `self._sessions: dict[str, str] = {}`
- [x] Remover métodos `get_session_id()` e `clear_session()`
- [x] Passar `db=self._db` e `session_id=conversation_id` ao criar Agent
- [x] Passar `add_history_to_context=True` e `num_history_runs=5` ao criar Agent
- [x] Atualizar daemon.py para passar `state_dir` ao instanciar AgnoAdapter
- [x] Testes: verificar que db e session_id são passados ao Agent

**Arquivos**: `src/adapters/agno_adapter.py` (MODIFY), `src/daemon.py` (MODIFY), `tests/adapters/test_agno_adapter.py` (MODIFY)

### Task 5: Remover _compress_prompt
- [x] Remover método `_compress_prompt()` do AgnoAdapter
- [x] No tratamento de context_length_exceeded, reduzir `num_history_runs` (ex: de 5→2→0) em vez de comprimir prompt
- [x] Manter `_compress_prompt` no `ClaudeAgentSDKAdapter` (não é afetado)
- [x] Atualizar testes: remover `TestCompressPrompt`, adicionar teste de redução de history_runs

**Arquivos**: `src/adapters/agno_adapter.py` (MODIFY), `tests/adapters/test_agno_adapter.py` (MODIFY)

### Task 6: Gerar function tools dinamicamente
- [x] Criar método `_generate_tools() -> list` que itera sobre `get_tool_definitions()`
- [x] Para cada definição, criar função async com nome, docstring e type hints dinâmicos
- [x] Remover método `_create_mcp_function_tools()` com as 11 funções explícitas
- [x] Atualizar `_build_agent_tools()` para chamar `_generate_tools()`
- [x] Testes: verificar que 11 tools são geradas, nomes corretos, chamada ao server funciona

**Arquivos**: `src/adapters/agno_adapter.py` (MODIFY), `tests/adapters/test_agno_adapter.py` (MODIFY)

### Task 7: Validação final
- [x] Rodar suite completa: `pytest tests/ -v`
- [x] Verificar 590+ testes passando (zero regressão) → 600 passed
- [x] Lint: `ruff check src/adapters/agno_adapter.py` → All checks passed
- [x] Format: `ruff format src/adapters/agno_adapter.py` → unchanged
- [x] Adapter reduzido de 517 → 463 linhas (-10%), com funcionalidades que antes não existiam (sessions reais, cache, tools dinâmicas)

**Arquivos**: Nenhum (validação apenas)
