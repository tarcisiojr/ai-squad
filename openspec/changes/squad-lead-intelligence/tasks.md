# Tasks: Squad Lead Intelligence

## Fase 0: Limpeza — Remover ClaudeCodeCLIAdapter

- [x] Deletar `src/adapters/claude_code.py`
- [x] Deletar `build/lib/src/adapters/claude_code.py`
- [x] Remover registro do provider `claude-code` em `src/factory.py`
- [x] Atualizar `platform.yaml`: `ai_provider: claude-agent-sdk`
- [x] Remover/atualizar testes que referenciam ClaudeCodeCLIAdapter
- [x] Verificar que nenhuma importação residual existe no codebase
- [x] Rodar `pytest` — todos os testes passam com SDK adapter

## Fase 1: Fundação (Journal + State Awareness)

- [x] Criar `src/orchestrator/journal.py` com classe JournalStore
  - [x] Método `create(demand_id, demand_text)` — cria journal vazio
  - [x] Método `add_decision(demand_id, action, detail)` — registra decisão
  - [x] Método `set_next_expected(demand_id, action, agent, description)` — define próxima ação
  - [x] Método `add_context_note(demand_id, note)` — nota de contexto
  - [x] Método `read(demand_id)` — lê journal
  - [x] Método `get_active_summaries()` — resumo formatado de journals ativos
  - [x] Método `get_stalled(stall_timeout)` — lista demandas paradas
  - [x] Escrita atômica (temp + rename)
- [x] Testes do JournalStore em `tests/test_journal.py`
  - [x] Teste CRUD básico (create, read, add_decision)
  - [x] Teste get_stalled com timeout
  - [x] Teste escrita atômica (crash safety)
  - [x] Teste get_active_summaries formatação

## Fase 2: Tools Novas no Engine

- [x] Implementar tool `get_demand_state()` no engine
  - [x] Sem argumentos: retorna todas demandas ativas
  - [x] Campo `stalled` calculado por timestamp
  - [x] Campo `next_expected_action` mapeado por estado
- [x] Implementar tool `read_journal()` no engine
  - [x] Retorna journal formatado para contexto do Squad Lead
- [x] Registrar ambas tools como MCP callbacks no `run_squad_lead()`
- [x] Testes das novas tools em `tests/test_engine_intelligence.py`

## Fase 3: Artifact-Based Completion (remover markers)

- [x] Remover sistema de markers do engine
  - [x] Reescrever `_verify_completion()` para usar Criteria Gate
  - [x] Feedback de retry com detalhes específicos (não "coloque o marker")
- [x] Testes da verificação artifact-based
  - [x] Teste PO conclusão detectada por artefatos
  - [x] Teste Dev conclusão detectada por tasks.md completo
  - [x] Teste QA conclusão detectada por report APROVADO
  - [x] Teste marker residual no output é ignorado (sem erro)

## Fase 4: check_artifacts() Enriquecido (Criteria Gate)

- [x] Enriquecer `_handle_check_artifacts()` com validações de qualidade
  - [x] Validar specs têm critérios de aceite (regex `- [ ]`)
  - [x] Validar tasks.md tem mínimo 3 itens
  - [x] Validar design.md existe
  - [x] Retorno estruturado com checks individuais
  - [x] Campo `action` sugerindo correção quando falha
- [x] Testes do check_artifacts enriquecido
  - [x] Teste specs sem critérios → falha
  - [x] Teste tasks vazio → falha
  - [x] Teste todos OK → passa
  - [x] Teste retorno estruturado

## Fase 5: Contexto Enriquecido no Engine

- [x] Modificar `run_squad_lead()` para injetar automaticamente:
  - [x] Resumo de demandas ativas (de StateManager)
  - [x] Status de agentes rodando (de RunningAgent)
  - [x] Resumo do journal (de JournalStore)
- [x] Integrar JournalStore no engine
  - [x] Criar journal quando nova demanda chega
  - [x] Registrar decisões automaticamente (start_agent, check_artifacts)
  - [x] Atualizar next_expected em cada transição
- [x] Testes da injeção de contexto

## Fase 6: AGENTS.md do Squad Lead (Reescrita)

- [x] Reescrever AGENTS.md com nova estrutura:
  - [x] Seção 1: Classificação de Intent (com exemplos por categoria)
  - [x] Seção 2: Consulta de Estado (instrução para ler contexto injetado)
  - [x] Seção 3: Tabela de Decisão (intent × estado → ação)
  - [x] Seção 4: Fluxo para Demandas Novas (mantido, refinado)
  - [x] Seção 5: Fluxo para Retomadas (NOVO)
  - [x] Seção 6: Validação de Artefatos (o que fazer quando falha)
  - [x] Seção 7: Comunicação (mantida)
- [x] Atualizar symlink CLAUDE.md → AGENTS.md

## Fase 7: Heartbeat Loop

- [x] Implementar `_heartbeat_loop()` no daemon
  - [x] Asyncio task que roda a cada `heartbeat_interval`
  - [x] Detecta demandas paradas via JournalStore.get_stalled()
  - [x] Retoma demandas paradas acionando Squad Lead
  - [x] Envia lembretes para demandas em awaiting_*_approval
  - [x] Respeita max_auto_retries por demanda
  - [x] Para gracefully no shutdown
- [x] Adicionar configuração em platform.yaml
  - [x] `heartbeat.enabled` (default: true)
  - [x] `heartbeat.interval` (default: 300)
  - [x] `heartbeat.stall_timeout` (default: 1800)
  - [x] `heartbeat.reminder_timeout` (default: 3600)
  - [x] `heartbeat.max_auto_retries` (default: 3)
- [x] Carregar config de heartbeat na PlatformConfig
- [x] Testes do heartbeat em `tests/test_heartbeat.py`
  - [x] Teste detecção de demanda parada
  - [x] Teste lembrete de aprovação
  - [x] Teste max retries respeitado

## Fase 8: Integração e Validação

- [x] Rodar `pytest --cov=src --cov-fail-under=80`
- [x] Verificar que todos os testes existentes continuam passando
