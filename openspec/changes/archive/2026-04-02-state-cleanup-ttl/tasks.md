## 1. Timestamp de conclusão

- [x] 1.1 Adicionar campo `done_at` (ISO 8601 UTC) no `set_state()` quando estado é `done` (`src/orchestrator/state.py`)
- [x] 1.2 Teste: `set_state("x", "done")` grava `done_at`, `set_state("x", "running")` não grava

## 2. Método cleanup_expired

- [x] 2.1 Implementar `cleanup_expired(ttl_days=7)` no `StateManager` — varre `*.json`, filtra `done` + `done_at` expirado, remove `.json` + subpasta `{demand_id}/`
- [x] 2.2 Validação: `ttl_days <= 0` levanta `ValueError`
- [x] 2.3 Retrocompatibilidade: demandas `done` sem `done_at` são ignoradas com log warning
- [x] 2.4 Testes: demanda expirada removida, demanda recente preservada, demanda em andamento ignorada, demanda legado sem done_at ignorada, artefatos duráveis preservados

## 3. Triggers de cleanup

- [x] 3.1 Chamar `cleanup_expired()` no boot do daemon (`src/daemon.py`), após inicializar StateManager
- [x] 3.2 Chamar `cleanup_expired()` no início de `run_squad_lead()` no engine (`src/orchestrator/engine.py`)
- [x] 3.3 Teste: verificar que cleanup é chamado nos dois pontos de entrada
