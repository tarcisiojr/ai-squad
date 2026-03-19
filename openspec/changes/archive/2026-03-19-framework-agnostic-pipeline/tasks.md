# Tasks: Framework-Agnostic Pipeline

## Fase 1 — Limpar (sem mudança de comportamento)

- [ ] Criar `src/orchestrator/atomic_write.py` com `write_json_atomic()` e `write_text_atomic()`
- [ ] Migrar `state.py`, `journal.py`, `conversation.py`, `daily_notes.py` para usar `atomic_write`
- [ ] Remover `src/orchestrator/docker.py` (`DockerAgentRunner` — código morto com vuln de injeção)
- [ ] Remover métodos legados do engine: `_invoke_agent`, `_invoke_parallel`, `run_demand_cycle`
- [ ] Remover alias `PersonaConfig = AgentConfig` se não usado externamente
- [ ] Corrigir bug: `_handle_human_needed` → usar `self._default_user_id` em vez de `"default"`
- [ ] Completar ABC `MessageBus`: adicionar `send_photo`, `send_typing` como métodos opcionais com default
- [ ] Corrigir mocks nos testes: herdar de ABCs, adicionar `**kwargs` em `send_message`
- [ ] Escrever testes para `LessonsStore` (add, get_relevant, format_for_prompt, migrate, count)
- [ ] Unificar `_verify_spec_completion` e `_check_artifacts_enriched` em `_collect_artifact_issues(change_dir)`
- [ ] Eliminar duplicação de `validate_required_tokens` entre Factory e Daemon
- [ ] Remover testes duplicados: consolidar test_adapters em test_claude_agent_sdk

## Fase 2 — Decompor engine (sem mudança de comportamento)

- [ ] Extrair `src/orchestrator/verification.py`: classify_agent_role, verify_completion, verify_spec/dev/review, check_artifacts_enriched
- [ ] Extrair `src/orchestrator/agent_manager.py`: start_agent_background, run_agent_work, on_agent_done, start_agent_retry, get_running_agents_status
- [ ] Extrair `src/orchestrator/prompt_builder.py`: get_agents_summary, read_agents_md, get_demand_state_summary, format_pipeline_state
- [ ] Extrair `src/orchestrator/media.py`: extract_and_send_images
- [ ] Adicionar campo `role: str = ""` ao `AgentConfig` no factory.py
- [ ] Parsear `role` do config.yaml por agente e usar em vez de `_classify_agent_role` por keywords
- [ ] Unificar `DemandState` (StateManager) e `current_phase` (Journal) — Journal como fonte de verdade
- [ ] Adaptar engine.py para usar os módulos extraídos (~500 linhas)
- [ ] Atualizar todos os testes para os módulos reorganizados
- [ ] Verificar cobertura ≥ 80% nos módulos novos

## Fase 3 — Pipeline declarativo

### 3.1 Infraestrutura de pipeline
- [ ] Criar `src/orchestrator/pipeline.py`: PipelineConfig, StepConfig, PipelineLoader
- [ ] Parsear `pipeline/pipeline.yaml` com validação de schema
- [ ] Parsear step files `.md` com frontmatter YAML e seções (Quality Gate, Veto Conditions)
- [ ] Criar `PipelineState` dataclass com persistência em `pipeline-state.json`
- [ ] Criar `StepExecution` dataclass substituindo `RunningAgent`

### 3.2 Quality gates
- [ ] Criar `QualityGateEvaluator` com dispatch automático (arquivo/estrutural/semântico)
- [ ] Implementar check de arquivo: `Path.exists()`, `stat().st_size`
- [ ] Implementar check estrutural: contar itens em YAML/JSON/Markdown checklists
- [ ] Implementar check semântico: chamada ao LLM para avaliação
- [ ] Migrar `OpenSpecValidator` como quality gate padrão do preset dev-openspec

### 3.3 Pipeline executor
- [ ] Criar `PipelineExecutor`: advance, skip, rerun, get_state
- [ ] Integrar PipelineExecutor no engine.py (substituir state machine hardcoded)
- [ ] Avançar automaticamente entre steps quando quality gate passa
- [ ] Pausar em checkpoints e notificar usuário
- [ ] Suportar `on_reject` para loops de revisão
- [ ] Suportar steps paralelos (`agents: [a, b]`)

### 3.4 MCP tools de pipeline
- [ ] Implementar `get_pipeline_state()` — retorna estado completo do pipeline
- [ ] Implementar `advance_step()` — avança manualmente para próximo step
- [ ] Implementar `skip_step(step_id)` — pula um step
- [ ] Implementar `rerun_step(step_id)` — re-executa um step
- [ ] Substituir `check_artifacts` por `verify_step` (roteia ao quality gate do step)

### 3.5 Squad Lead com visão de pipeline
- [ ] Injetar pipeline state no prompt do Squad Lead (prompt_builder)
- [ ] Atualizar AGENTS.md do squad-lead: instruções genéricas baseadas em pipeline
- [ ] Squad Lead recebe lista de steps + status + quality gates no contexto

### 3.6 Agentes com frontmatter
- [ ] Parser de frontmatter YAML em AGENTS.md
- [ ] Extrair: name, domain, role, model_tier, triggers, outputs
- [ ] Usar `role` do frontmatter em vez de `_classify_agent_role` por keywords
- [ ] Usar `model_tier` do frontmatter para routing por agente

### 3.7 Presets
- [ ] Criar `src/presets/dev-openspec/` com pipeline, steps e agents completos
- [ ] Criar `src/presets/infra-monitor/` com pipeline Triager → SRE → Validator
- [ ] Atualizar CLI `ai-squad create --preset <nome>` para copiar template
- [ ] Testar: time criado com preset dev-openspec funciona identicamente ao atual
- [ ] Testar: time criado com preset infra-monitor funciona sem referência a openspec

### 3.8 Retrocompatibilidade
- [ ] Se `pipeline/pipeline.yaml` não existe, engine opera no modo legado (comportamento atual)
- [ ] Migrar states existentes de DemandState para pipeline-state.json no primeiro uso
- [ ] Documentar migração em CLAUDE.md

### 3.9 Testes e validação final
- [ ] Testes unitários para PipelineLoader (yaml válido, inválido, step files)
- [ ] Testes unitários para QualityGateEvaluator (arquivo, estrutural, semântico)
- [ ] Testes unitários para PipelineExecutor (advance, skip, rerun, checkpoint)
- [ ] Testes de integração: pipeline dev-openspec end-to-end
- [ ] Testes de integração: pipeline infra-monitor end-to-end
- [ ] Cobertura total ≥ 80%
- [ ] Verificar zero referências hardcoded a "openspec" no engine
- [ ] Atualizar CLAUDE.md com nova arquitetura
