## MODIFIED Requirements

### Requirement: Despacho de agentes via adapter
O orquestrador SHALL disparar agentes exclusivamente via `AIAgentAdapter` interface. O orquestrador SHALL NOT importar ou conhecer implementações concretas de IA. O engine SHALL ser decomposto em 3 módulos: `engine.py` (core ≤600 LOC), `prompt_builder.py` (montagem de contexto), `pipeline_handler.py` (callbacks de pipeline). Imports públicos SHALL ser mantidos no `__init__.py` do orchestrator.

#### Scenario: Despacho de agente PO
- **WHEN** uma demanda entra no estado `po_working`
- **THEN** o orquestrador invoca o adapter com o prompt e contexto do agente PO registrado no registry

#### Scenario: Engine decomposto em 3 módulos
- **WHEN** o módulo orchestrator é inspecionado
- **THEN** existe `engine.py` (≤600 LOC), `prompt_builder.py` e `pipeline_handler.py`
- **AND** `engine.py` importa e delega para os outros dois módulos

### Requirement: Prompt otimizado com contexto incremental
O prompt builder SHALL cachear partes estáticas do contexto (AGENTS.md, workspace context) e só reconstruir quando houver mudança. Partes dinâmicas (journal, pipeline state) SHALL ser incluídas apenas quando relevantes à demanda atual.

#### Scenario: Cache de contexto estático
- **WHEN** `build_squad_lead_prompt()` é chamado 2 vezes sem mudança em AGENTS.md
- **THEN** AGENTS.md é lido do cache na segunda chamada (sem I/O)

#### Scenario: Contexto dinâmico filtrado
- **WHEN** o prompt é montado para uma demanda sem pipeline ativo
- **THEN** a seção de pipeline state SHALL NOT ser incluída no prompt

## ADDED Requirements

### Requirement: Pipeline handler isolado
O módulo `pipeline_handler.py` SHALL conter os callbacks: `handle_get_pipeline_state()`, `handle_advance_step()`, `handle_skip_step()`, `handle_rerun_step()`. Estes callbacks SHALL ser registrados no engine via callback registry.

#### Scenario: Pipeline handler registrado no engine
- **WHEN** o engine inicializa
- **THEN** os 4 callbacks de pipeline são registrados via `on(event, handler)`

#### Scenario: Advance step via pipeline handler
- **WHEN** o Squad Lead invoca `advance_step()`
- **THEN** o pipeline handler processa e retorna o resultado ao engine
