# Proposal: Framework-Agnostic Pipeline

## Problema

O ai-dev-team está **acoplado ao OpenSpec** e a um fluxo de desenvolvimento de software (PO → Dev → Review → QA). Isso impede dois cenários legítimos:

1. **Times não-dev**: um time de infra/monitoramento (Triager → SRE → Validator) não funciona porque o engine assume estados como `PO_WORKING`, `DEV_WORKING`, `QA_VALIDATING` e valida artefatos como `proposal.md`, `tasks.md`.

2. **Times dev sem OpenSpec**: um time que usa outra metodologia (kanban simples, tickets lineares) não consegue usar a plataforma porque a verificação de artefatos está amarrada à estrutura `openspec/changes/`.

### Evidências do acoplamento (mapeamento completo)

| Tipo | Localização | Detalhe |
|------|-------------|---------|
| Path hardcoded | engine.py L758, L854, L918 | `"openspec/changes/"` |
| Arquivos fixos | engine.py L773 | `["proposal.md", "design.md", "tasks.md"]` |
| Formato fixo | engine.py L805, L945 | `"- [ ]"` / `"- [x]"` como validação |
| Estados fixos | models.py | `DemandState` enum com PO/DEV/QA |
| Keywords fixas | engine.py L711-716 | `"openspec"`, `"tasks.md"`, `"aprovado"` |
| Nomes fixos | engine.py L153, L1099 | `"dev"`, `"squad-lead"` hardcoded |
| Lógica duplicada | engine.py L754 vs L915 | Dois métodos verificam os mesmos artefatos |

### Problemas adicionais identificados na revisão

- **God object**: engine.py tem 1481 linhas e 48 métodos com 10 responsabilidades distintas
- **Duas fontes de verdade**: `DemandState` (StateManager) e `current_phase` (Journal) rastreiam o mesmo ciclo sem sincronização
- **Escrita atômica duplicada** em 4 módulos (state, journal, conversation, daily_notes)
- **Código morto**: `DockerAgentRunner` (com vuln de injeção), `_invoke_agent`, `_invoke_parallel`, `run_demand_cycle`
- **Mocks divergentes**: testes não herdam das ABCs, mascarando bugs de assinatura
- **LessonsStore sem testes**: 0% cobertura de funcionalidade crítica de inteligência
- **Bug real**: `_handle_human_needed` usa `user_id="default"` em vez de `self._default_user_id`

## Solução

Transformar o engine de um **orquestrador hardcoded** em um **executor de pipeline declarativo**, em 3 fases incrementais que preservam a inteligência existente (sumarização, lessons, journal, daily notes, model routing) e adicionam flexibilidade.

### Fase 1 — Limpar (sem mudança de comportamento)

Remover redundâncias, código morto, corrigir bugs e preparar a base.

- Unificar escrita atômica em `atomic_write.py`
- Remover código morto: `DockerAgentRunner`, `_invoke_agent`, `_invoke_parallel`, `run_demand_cycle`
- Corrigir bug `user_id="default"` em `_handle_human_needed`
- Corrigir mocks nos testes (herdar de ABCs, adicionar `**kwargs`)
- Escrever testes para `LessonsStore`
- Unificar `_verify_spec_completion` e `_check_artifacts_enriched` em método compartilhado
- Completar ABC `MessageBus` com `send_photo`, `send_typing`

### Fase 2 — Decompor engine (sem mudança de comportamento)

Extrair responsabilidades do god object em módulos coesos.

```
engine.py (1481 linhas) → 6 módulos:
  ├── verification.py     (~250 linhas) — validação de artefatos
  ├── agent_manager.py    (~300 linhas) — ciclo de vida de agentes
  ├── prompt_builder.py   (~200 linhas) — montagem de contexto
  ├── media.py            (~100 linhas) — detecção e envio de imagens
  ├── atomic_write.py     (~30 linhas)  — escrita atômica compartilhada
  └── engine.py           (~500 linhas) — core: Squad Lead + state machine
```

Adicionar campo `role` ao `AgentConfig` para substituir `_classify_agent_role` por keywords.

Unificar `DemandState` + `current_phase` do Journal em fonte de verdade única.

### Fase 3 — Pipeline declarativo (Opção C)

Externalizar fluxo, validação e estados em arquivos de configuração.

#### 3.1 Pipeline YAML

Cada time define seu fluxo em `pipeline/pipeline.yaml`:

```yaml
# Time de dev com OpenSpec
pipeline:
  steps:
    - id: especificacao
      agent: po
      type: checkpoint
      file: steps/step-01-spec.md

    - id: implementacao
      agents: [dev-backend, dev-frontend]
      execution: background
      file: steps/step-02-dev.md

    - id: revisao
      agent: code-review
      type: checkpoint
      file: steps/step-03-review.md

    - id: qualidade
      agent: qa
      file: steps/step-04-qa.md
```

```yaml
# Time de infra
pipeline:
  steps:
    - id: triagem
      agent: triager
      file: steps/step-01-triage.md

    - id: remediacao
      agent: sre
      execution: background
      file: steps/step-02-remediate.md

    - id: validacao
      agent: validator
      type: checkpoint
      file: steps/step-03-validate.md
```

#### 3.2 Step files com Quality Gates

Cada step é um Markdown com frontmatter (inspirado no OpenSquad):

```markdown
---
step: "01"
name: "Especificação"
type: agent
agent: po
execution: subagent
model_tier: powerful
on_reject: step-01
---

# Step 01: Especificação

## Inputs
- Mensagem do usuário com a demanda

## Expected Outputs
- openspec/changes/<slug>/proposal.md
- openspec/changes/<slug>/design.md
- openspec/changes/<slug>/tasks.md
- openspec/changes/<slug>/specs/**/*.md

## Quality Gate
- [ ] proposal.md existe e tem mais de 50 bytes
- [ ] design.md existe
- [ ] tasks.md tem pelo menos 3 itens
- [ ] Cada spec tem critérios de aceite (checklist)

## Veto Conditions
- tasks.md com menos de 3 itens
- Spec sem nenhum critério de aceite
```

#### 3.3 Modelo de execução: Híbrido (pipeline auto + Squad Lead override)

```
Pipeline avança automaticamente entre steps.
Quality gates são avaliados pelo engine (estruturais) e LLM (semânticos).
Checkpoints pausam para aprovação humana.
Squad Lead pode override: pular, reordenar, re-rodar steps via MCP tools.
```

Novas MCP tools:
- `get_pipeline_state()` — estado completo do pipeline
- `advance_step()` — avança manualmente
- `skip_step(step_id)` — pula um step
- `rerun_step(step_id)` — re-executa um step

#### 3.4 Estado derivado do pipeline

Em vez de `DemandState` enum fixo:

```python
# Estado = step atual do pipeline
# "especificacao" → "implementacao" → "revisao" → "qualidade" → "done"
# Derivado de pipeline.yaml, não de código Python
```

Persistido em `state/{demand_id}/pipeline-state.json`:

```json
{
  "demand_id": "d-001",
  "pipeline": "dev-openspec",
  "current_step": "implementacao",
  "steps": {
    "especificacao": {"status": "completed", "agent": "po", "quality_gate": "passed"},
    "implementacao": {"status": "running", "agents": ["dev-backend"], "agent_status": {"dev-backend": "running"}},
    "revisao": {"status": "pending"},
    "qualidade": {"status": "pending"}
  }
}
```

#### 3.5 Tracking: quem puxou qual tarefa

```python
# Substitui _running_agents: dict[str, RunningAgent]
# Por execuções indexadas por (demand, step):

@dataclass
class StepExecution:
    demand_id: str
    step_id: str
    agents: list[str]
    status: str  # pending, running, completed, failed
    agent_status: dict[str, str]  # agent → running/done/error
    agent_tasks: dict[str, asyncio.Task]
    retries: int = 0
```

Índice reverso para consulta:
```python
def get_agent_allocation(self, agent_name) -> list[StepExecution]
```

#### 3.6 Presets pré-configurados

```bash
ai-dev-team create --preset dev-openspec backend-api --repo ~/api
ai-dev-team create --preset infra-monitor monitoring --repo ~/infra
ai-dev-team create --preset content-squad marketing
```

Cada preset gera a estrutura completa: `pipeline/`, `agents/`, `steps/`.

## O que NÃO muda

A inteligência existente é **preservada e reutilizada**:

| Capacidade | Status |
|-----------|--------|
| Sumarização automática de contexto | Mantida — independe de pipeline |
| Model routing por complexidade | Mantido — aplicado ao Squad Lead |
| Notas diárias | Mantidas — registram eventos genéricos |
| Lessons learned (FTS5) | Mantido — learning entre demandas |
| Journal de decisões | Adaptado — vinculado a steps do pipeline |
| Conversation history | Mantido — por demanda |
| Retry com backoff exponencial | Mantido — no adapter |
| Monitor de respostas vazias | Mantido — no engine core |
| Heartbeat loop | Adaptado — verifica pipeline state em vez de DemandState |

## Escopo e não-escopo

### Escopo
- Desacoplar engine do OpenSpec
- Pipeline declarativo em YAML
- Step files com quality gates
- Decomposição do engine em módulos
- Limpeza de código morto e redundâncias
- Presets para criação rápida de times

### Não-escopo
- Fila de tarefas com prioridade (v2)
- UI/dashboard web para visualização (v2)
- Marketplace de agentes/skills (v2)
- Multi-tenancy (v2)

## Métricas de sucesso

- [ ] Um time de infra (Triager → SRE → Validator) funciona sem modificação de código Python
- [ ] O time de dev existente (com OpenSpec) continua funcionando identicamente via preset
- [ ] engine.py reduzido de ~1500 para ~500 linhas
- [ ] Zero referências hardcoded a "openspec", "proposal.md", "tasks.md" no engine
- [ ] Cobertura de testes ≥ 80% nos novos módulos
- [ ] Todos os testes existentes continuam passando

## Riscos

| Risco | Mitigação |
|-------|-----------|
| Regressão no fluxo de dev existente | Preset dev-openspec gera exatamente a config atual; testes end-to-end |
| Complexidade do PipelineExecutor | Fase 2 (decomposição) prepara a base; Fase 3 é incremental |
| Quality gates por LLM custam tokens | Verificações estruturais (arquivo existe, tamanho) resolvidas em código; LLM só para semântica |
| Squad Lead perde contexto com pipeline | Injeção do pipeline state completo no prompt (visão total) |
