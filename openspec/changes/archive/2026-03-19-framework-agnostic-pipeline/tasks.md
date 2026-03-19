# Tasks: Framework-Agnostic Pipeline

## Fase 1 — Limpar (sem mudança de comportamento)

- [x] Criar `src/orchestrator/atomic_write.py` com `write_json_atomic()` e `write_text_atomic()`
- [x] Migrar `state.py`, `journal.py`, `conversation.py`, `daily_notes.py` para usar `atomic_write`
- [x] Remover `src/orchestrator/docker.py` (`DockerAgentRunner` — código morto com vuln de injeção)
- [x] Remover métodos legados do engine: `_invoke_agent`, `_invoke_parallel`, `run_demand_cycle`
- [x] Remover alias `PersonaConfig = AgentConfig` se não usado externamente
- [x] Corrigir bug: `_handle_human_needed` → usar `self._default_user_id` em vez de `"default"`
- [x] Completar ABC `MessageBus`: adicionar `send_photo`, `send_typing` como métodos opcionais com default
- [x] Corrigir mocks nos testes: herdar de ABCs, adicionar `**kwargs` em `send_message`
- [x] Escrever testes para `LessonsStore` (add, get_relevant, format_for_prompt, migrate, count)
- [x] Unificar `_verify_spec_completion` e `_check_artifacts_enriched` em `_collect_artifact_issues(change_dir)`
- [x] Eliminar duplicação de `validate_required_tokens` entre Factory e Daemon
- [x] Remover testes duplicados: consolidar test_adapters em test_claude_agent_sdk

## Fase 2 — Decompor engine (sem mudança de comportamento)

- [x] Extrair `src/orchestrator/verification.py`: classify_agent_role, verify_completion, verify_spec/dev/review, check_artifacts_enriched
- [x] Extrair `src/orchestrator/agent_manager.py`: start_agent_background, run_agent_work, on_agent_done, start_agent_retry, get_running_agents_status
- [x] Extrair `src/orchestrator/prompt_builder.py`: get_agents_summary, read_agents_md, get_demand_state_summary, format_pipeline_state
- [x] Extrair `src/orchestrator/media.py`: extract_and_send_images
- [x] Adicionar campo `role: str = ""` ao `AgentConfig` no factory.py
- [x] Parsear `role` do config.yaml por agente e usar em vez de `_classify_agent_role` por keywords
- [x] Unificar `DemandState` (StateManager) e `current_phase` (Journal) — Journal como fonte de verdade
- [x] Adaptar engine.py para usar os módulos extraídos (~500 linhas)
- [x] Atualizar todos os testes para os módulos reorganizados
- [x] Verificar cobertura ≥ 80% nos módulos novos

## Fase 3 — Pipeline declarativo

### 3.1 Infraestrutura de pipeline
- [x] Criar `src/orchestrator/pipeline.py`: PipelineConfig, StepConfig, PipelineLoader
- [x] Parsear `pipeline/pipeline.yaml` com validação de schema
- [x] Parsear step files `.md` com frontmatter YAML e seções (Quality Gate, Veto Conditions)
- [x] Criar `PipelineState` dataclass com persistência em `pipeline-state.json`
- [x] Criar `StepExecution` dataclass substituindo `RunningAgent`

### 3.2 Quality gates
- [x] Criar `QualityGateEvaluator` com dispatch automático (arquivo/estrutural/semântico)
- [x] Implementar check de arquivo: `Path.exists()`, `stat().st_size`
- [x] Implementar check estrutural: contar itens em YAML/JSON/Markdown checklists
- [x] Implementar check semântico: chamada ao LLM para avaliação
- [x] Migrar `OpenSpecValidator` como quality gate padrão do preset dev-openspec

### 3.3 Pipeline executor
- [x] Criar `PipelineExecutor`: advance, skip, rerun, get_state
- [x] Integrar PipelineExecutor no engine.py (substituir state machine hardcoded)
- [x] Avançar automaticamente entre steps quando quality gate passa
- [x] Pausar em checkpoints e notificar usuário
- [x] Suportar `on_reject` para loops de revisão
- [x] Suportar steps paralelos (`agents: [a, b]`)

### 3.4 MCP tools de pipeline
- [x] Implementar `get_pipeline_state()` — retorna estado completo do pipeline
- [x] Implementar `advance_step()` — avança manualmente para próximo step
- [x] Implementar `skip_step(step_id)` — pula um step
- [x] Implementar `rerun_step(step_id)` — re-executa um step
- [x] Substituir `check_artifacts` por `verify_step` (roteia ao quality gate do step)

### 3.5 Squad Lead com visão de pipeline
- [x] Injetar pipeline state no prompt do Squad Lead (prompt_builder)
- [x] Atualizar AGENTS.md do squad-lead: instruções genéricas baseadas em pipeline
- [x] Squad Lead recebe lista de steps + status + quality gates no contexto

### 3.6 Agentes com frontmatter
- [x] Parser de frontmatter YAML em AGENTS.md
- [x] Extrair: name, domain, role, model_tier, triggers, outputs
- [x] Usar `role` do frontmatter em vez de `_classify_agent_role` por keywords
- [x] Usar `model_tier` do frontmatter para routing por agente

### 3.7 Presets
- [x] Criar `src/presets/dev-openspec/` com pipeline, steps e agents completos
- [x] Criar `src/presets/infra-monitor/` com pipeline Triager → SRE → Validator
- [x] Atualizar CLI `ai-squad create --preset <nome>` para copiar template
- [x] Testar: time criado com preset dev-openspec funciona identicamente ao atual
- [x] Testar: time criado com preset infra-monitor funciona sem referência a openspec

### 3.8 Retrocompatibilidade
- [x] Se `pipeline/pipeline.yaml` não existe, engine opera no modo legado (comportamento atual)
- [x] Migrar states existentes de DemandState para pipeline-state.json no primeiro uso
- [x] Documentar migração em CLAUDE.md

### 3.9 Testes e validação final
- [x] Testes unitários para PipelineLoader (yaml válido, inválido, step files)
- [x] Testes unitários para QualityGateEvaluator (arquivo, estrutural, semântico)
- [x] Testes unitários para PipelineExecutor (advance, skip, rerun, checkpoint)
- [x] Testes de integração: pipeline dev-openspec end-to-end
- [x] Testes de integração: pipeline infra-monitor end-to-end
- [x] Cobertura total ≥ 80%
- [x] Verificar zero referências hardcoded a "openspec" no engine
- [x] Atualizar CLAUDE.md com nova arquitetura
