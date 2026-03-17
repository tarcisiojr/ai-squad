# Spec: Core — Pipeline Declarativo Framework-Agnostic

## Capacidades

### C1. Pipeline YAML
- [ ] Engine lê `pipeline/pipeline.yaml` para determinar o fluxo de steps
- [ ] Cada step declara: id, name, agent(s), type, execution mode, file
- [ ] Steps paralelos suportados via `agents: [a, b]`
- [ ] Steps sequenciais avançam automaticamente quando quality gate passa
- [ ] Checkpoints (`type: checkpoint`) pausam para aprovação humana
- [ ] `on_reject` permite loops de revisão (retorno a step anterior)

### C2. Step Files
- [ ] Cada step é um arquivo Markdown com frontmatter YAML
- [ ] Frontmatter define: step, name, type, agent, execution, model_tier, on_reject
- [ ] Corpo define: instruções, inputs, expected outputs, quality gate, veto conditions
- [ ] Engine parseia frontmatter e seções para configuração automática

### C3. Quality Gates Híbridos
- [ ] Verificações de arquivo (`existe`, `tamanho > N bytes`) resolvidas por código
- [ ] Verificações estruturais (`contém N itens`, `formato YAML válido`) resolvidas por código quando possível
- [ ] Verificações semânticas (`conteúdo relevante`, `sem contradições`) avaliadas pelo LLM
- [ ] Veto conditions avaliadas automaticamente antes de avançar
- [ ] Retry automático (até `max_retries`) quando quality gate falha
- [ ] Após `max_retries`, notifica Squad Lead para decisão

### C4. Pipeline State
- [ ] Estado persistido em `state/{demand_id}/pipeline-state.json`
- [ ] Cada step tem status: pending, running, checkpoint, completed, failed
- [ ] Agentes alocados por step com status individual
- [ ] Timestamp de início/conclusão por step
- [ ] Resultado do quality gate por step
- [ ] `DemandState` enum removido; estado derivado do pipeline

### C5. Squad Lead com Visão Total
- [ ] Pipeline state completo injetado no prompt do Squad Lead
- [ ] Squad Lead vê: steps completados, step atual, steps pendentes, quality gates
- [ ] Squad Lead vê allocation de agentes por step
- [ ] MCP tools: `get_pipeline_state()`, `advance_step()`, `skip_step()`, `rerun_step()`
- [ ] Squad Lead pode override automação (pular, reordenar, re-rodar)

### C6. StepExecution como Unidade de Tracking
- [ ] `StepExecution` substitui `RunningAgent` como unidade de tracking
- [ ] Indexado por `(demand_id, step_id)`
- [ ] Suporta múltiplos agentes por step (paralelo)
- [ ] Índice reverso: agent → list[StepExecution] para consulta de allocation
- [ ] Impede alocação dupla do mesmo agente

### C7. Decomposição do Engine
- [ ] `verification.py` — quality gates e validators
- [ ] `agent_manager.py` — ciclo de vida de agentes
- [ ] `prompt_builder.py` — montagem de contexto para prompts
- [ ] `media.py` — detecção e envio de imagens/arquivos
- [ ] `atomic_write.py` — escrita atômica compartilhada
- [ ] `pipeline.py` — parser de pipeline.yaml e step files
- [ ] `engine.py` core reduzido a ~500 linhas

### C8. Agentes com Frontmatter
- [ ] AGENTS.md suporta frontmatter YAML com: name, domain, role, model_tier, triggers, outputs
- [ ] Engine parseia frontmatter para metadata estruturada
- [ ] Campo `role` substitui `_classify_agent_role()` por keywords
- [ ] Campo `model_tier` permite routing por agente (não só Squad Lead)

### C9. Presets
- [ ] `ai-dev-team create --preset dev-openspec` gera pipeline + agents + steps completos
- [ ] Preset `dev-openspec` reproduz o fluxo atual (PO → Dev → Review → QA)
- [ ] Preset `infra-monitor` gera fluxo Triager → SRE → Validator
- [ ] Presets armazenados em `src/presets/` como templates copiáveis
- [ ] CLI copia template para `~/.ai-dev-team/teams/{nome}/`

### C10. Limpeza e Correções
- [ ] Código morto removido: DockerAgentRunner, _invoke_agent, _invoke_parallel, run_demand_cycle
- [ ] Bug corrigido: `_handle_human_needed` usa `self._default_user_id`
- [ ] Escrita atômica unificada em `atomic_write.py` (4 implementações → 1)
- [ ] ABC `MessageBus` completa: `send_photo`, `send_typing` declarados
- [ ] Mocks nos testes herdam das ABCs reais
- [ ] `LessonsStore` com cobertura de testes ≥ 90%
- [ ] Nomes de agentes dinâmicos (zero hardcode de "dev", "squad-lead")
- [ ] `DemandState` + `current_phase` unificados em fonte de verdade única

## Retrocompatibilidade

- [ ] Time de dev existente funciona identicamente via preset `dev-openspec`
- [ ] `check_artifacts` MCP tool funciona via `QualityGateEvaluator` (roteado ao validator do step)
- [ ] Conversation history, lessons, journal, daily notes preservados sem migração
- [ ] `config.yaml` existente continua funcionando (pipeline é opcional, default = comportamento atual)
