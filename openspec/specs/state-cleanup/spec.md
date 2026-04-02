# state-cleanup

## Purpose

Expurgo automático de demandas concluídas após TTL configurável, mantendo a pasta state/ limpa sem intervenção manual. Preserva artefatos de conhecimento durável (lessons, graph, daily).

## Requirements

### Requirement: Registro de timestamp de conclusão
O StateManager SHALL registrar um campo `done_at` (ISO 8601 UTC) no JSON da demanda quando o estado muda para `done`. O campo SHALL ser persistido atomicamente junto com a transição de estado.

#### Scenario: Demanda concluída recebe timestamp
- **WHEN** `set_state(demand_id, "done")` é chamado
- **THEN** o JSON da demanda contém `done_at` com o datetime UTC atual em formato ISO 8601

#### Scenario: Transição para outro estado não grava done_at
- **WHEN** `set_state(demand_id, "running")` é chamado
- **THEN** o JSON da demanda NÃO contém campo `done_at`

### Requirement: Cleanup de demandas expiradas
O StateManager SHALL expor um método `cleanup_expired(ttl_days=7)` que remove demandas em estado `done` cujo `done_at` é anterior a `now - ttl_days`. O cleanup SHALL remover o arquivo `.json` de estado E a subpasta associada (conversation, journal, pipeline-state).

#### Scenario: Demanda concluída há mais de 7 dias é removida
- **WHEN** `cleanup_expired()` é executado e existe demanda com `done_at` de 10 dias atrás
- **THEN** o arquivo `{demand_id}.json` é removido E a pasta `{demand_id}/` é removida recursivamente

#### Scenario: Demanda concluída há menos de 7 dias é preservada
- **WHEN** `cleanup_expired()` é executado e existe demanda com `done_at` de 3 dias atrás
- **THEN** o arquivo `{demand_id}.json` e a pasta `{demand_id}/` são mantidos

#### Scenario: Demanda em andamento nunca é removida
- **WHEN** `cleanup_expired()` é executado e existe demanda com estado `running`
- **THEN** a demanda é ignorada independente da sua idade

#### Scenario: Demanda done sem done_at é ignorada
- **WHEN** `cleanup_expired()` é executado e existe demanda `done` sem campo `done_at` (legado)
- **THEN** a demanda é ignorada (não é removida) para retrocompatibilidade

### Requirement: Preservação de artefatos duráveis
O cleanup SHALL preservar arquivos e diretórios de conhecimento durável: `lessons.db`, `graph.db`, `daily/`, `squad-lead-session/`, `tui.log`. O cleanup SHALL operar exclusivamente sobre arquivos `{demand_id}.json` e pastas `{demand_id}/`.

#### Scenario: lessons.db não é afetado pelo cleanup
- **WHEN** `cleanup_expired()` é executado
- **THEN** `lessons.db`, `graph.db`, `daily/` e `squad-lead-session/` permanecem intactos

### Requirement: TTL configurável
O TTL SHALL ser configurável via parâmetro com default de 7 dias. O valor MUST ser um inteiro positivo.

#### Scenario: TTL customizado
- **WHEN** `cleanup_expired(ttl_days=14)` é chamado
- **THEN** somente demandas concluídas há mais de 14 dias são removidas

#### Scenario: TTL inválido rejeitado
- **WHEN** `cleanup_expired(ttl_days=0)` ou `cleanup_expired(ttl_days=-1)` é chamado
- **THEN** o sistema levanta `ValueError`
