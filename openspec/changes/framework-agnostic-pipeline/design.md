# Design: Framework-Agnostic Pipeline

## Visão Arquitetural

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ANTES                                        │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     engine.py (1481 linhas)                  │   │
│  │                                                              │   │
│  │  Estado (DemandState enum fixo)                              │   │
│  │  + Agentes (nomes hardcoded: "dev", "squad-lead")           │   │
│  │  + Verificação (openspec/changes/, proposal.md, etc)        │   │
│  │  + Classificação (keywords no AGENTS.md)                    │   │
│  │  + Prompt building + Media + Conversa + Retry + ...         │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                         DEPOIS                                       │
│                                                                      │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────────┐    │
│  │ pipeline.yaml │  │  step files   │  │  agents/ AGENTS.md   │    │
│  │ (fluxo)       │  │ (quality gate)│  │  (personas)          │    │
│  └───────┬───────┘  └───────┬───────┘  └──────────┬───────────┘    │
│          │                  │                      │                 │
│          ▼                  ▼                      ▼                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     engine.py (~500 linhas)                  │   │
│  │  PipelineExecutor: lê pipeline, avança steps                │   │
│  │  Squad Lead: coordena, override, checkpoints                │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │  agent_manager.py     │  verification.py    │ prompt_builder │   │
│  │  ciclo de vida        │  quality gates      │ contexto       │   │
│  │  step executions      │  validators ABC     │ pipeline state │   │
│  └───────────────────────┴─────────────────────┴────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Decisões de Design

### D1. Pipeline como configuração, não como código

**Decisão**: O fluxo de trabalho é definido em `pipeline/pipeline.yaml`, não em Python.

**Alternativas consideradas**:
- Pipeline como código Python (classes Step, decorators) — rejeitado: exige conhecimento de Python para customizar
- Pipeline como JSON — rejeitado: YAML é mais legível e suporta comentários

**Consequência**: Qualquer pessoa pode criar um pipeline editando YAML. O engine não precisa saber o domínio.

### D2. Quality gates híbridos (código + LLM)

**Decisão**: Verificações declaradas no step file. O engine resolve automaticamente:
- Verificações de arquivo (existe, tamanho) → código determinístico
- Verificações estruturais (N itens, formato) → código quando possível
- Verificações semânticas (qualidade, coerência) → LLM avalia

**Padrão de detecção automática**:
```
"- [ ] output/file.yaml existe"       → engine verifica Path.exists()
"- [ ] Contém pelo menos 3 itens"     → engine conta itens se YAML/JSON
"- [ ] Conteúdo é relevante ao tema"  → LLM avalia
```

**Alternativas consideradas**:
- Validators como código Python plugável (ABC) — mantido como opção para casos avançados
- Tudo via LLM (estilo OpenSquad) — rejeitado: caro e não-determinístico para checks triviais

### D3. Modelo C — Pipeline auto + Squad Lead override

**Decisão**: O engine avança o pipeline automaticamente. O Squad Lead tem visão total e pode fazer override via MCP tools.

```
                 Fluxo normal (automático)
step-01 ──────▶ step-02 ──────▶ checkpoint ──────▶ step-03
  │                │                 │                 │
  │ quality gate   │ quality gate    │ humano          │ quality gate
  │ (auto)         │ (auto)         │ decide          │ (auto)
  │                │                 │                 │
  └── se falha:    └── se falha:    └── se rejeita:   │
      retry            retry            on_reject     │
      (auto)           (auto)           → step-N      │
                                                       │
                 Squad Lead override (manual)           │
                 skip_step, rerun_step, advance_step ──┘
```

**Alternativas consideradas**:
- Model A (100% automático) — rejeitado: sem flexibilidade para improvisos
- Model B (100% Squad Lead) — rejeitado: é o modelo atual, pouco previsível

### D4. Estado derivado do pipeline

**Decisão**: Eliminar `DemandState` enum. Estado = step atual do pipeline.

**Migração**:
```
DemandState.PO_WORKING         → pipeline step "especificacao" running
DemandState.AWAITING_PLAN_APPROVAL → pipeline step "especificacao" checkpoint
DemandState.DEV_WORKING         → pipeline step "implementacao" running
DemandState.AWAITING_PR_APPROVAL → pipeline step "revisao" checkpoint
DemandState.CI_RUNNING          → pipeline step "ci" running
DemandState.QA_VALIDATING       → pipeline step "qualidade" running
DemandState.DONE                → pipeline status "completed"
```

**Retrocompatibilidade**: `VALID_TRANSITIONS` deixa de existir no Python; as transições são definidas pela ordem dos steps no pipeline.yaml.

### D5. Estrutura de diretórios por time

```
~/.ai-dev-team/teams/{nome}/
├── config.yaml                 # providers, timeouts, model tiers
├── .env                        # tokens (gitignored)
├── pipeline/
│   ├── pipeline.yaml           # definição do fluxo
│   └── steps/
│       ├── step-01-spec.md     # cada step com quality gate
│       ├── step-02-dev.md
│       └── ...
├── agents/
│   ├── po/
│   │   └── AGENTS.md           # persona completa
│   ├── dev-backend/
│   │   └── AGENTS.md
│   └── ...
└── state/                      # runtime (gitignored)
    ├── daily/
    ├── lessons.db
    └── {demand_id}/
        ├── pipeline-state.json
        ├── conversation.json
        └── squad-lead-journal.json
```

### D6. Agentes com frontmatter estruturado

AGENTS.md evolui para incluir metadata parseable:

```markdown
---
name: SRE
domain: infrastructure
role: executor
model_tier: powerful
triggers:
  - incident classified as P1/P2
  - manual escalation
outputs:
  - runbook executed
  - metrics normalized
---

## Persona
Você é um SRE experiente...

## Dominio
Infraestrutura e monitoramento...

## Quando Envolver
- Incidente classificado
- Necessidade de rollback
```

O engine parseia o frontmatter para `role`, `model_tier`, `triggers`, `outputs` — eliminando a heurística de keywords.

### D7. Decomposição do engine

| Módulo | Responsabilidade | Tamanho estimado |
|--------|-----------------|-----------------|
| `engine.py` | Core: Squad Lead, pipeline executor, state machine, MCP callbacks | ~500 linhas |
| `agent_manager.py` | Ciclo de vida: start, run, done, retry, status | ~300 linhas |
| `verification.py` | Quality gates: dispatch, validators, artifact checks | ~250 linhas |
| `prompt_builder.py` | Montagem de contexto: agents summary, pipeline state, demand state | ~200 linhas |
| `media.py` | Detecção e envio de imagens/arquivos em respostas | ~100 linhas |
| `atomic_write.py` | Utilitário compartilhado de escrita atômica | ~30 linhas |
| `pipeline.py` | Parser de pipeline.yaml e step files | ~150 linhas |

### D8. StepExecution como unidade de tracking

```python
@dataclass
class StepExecution:
    """Execução de um step do pipeline para uma demanda."""
    demand_id: str
    step_id: str
    step_config: dict           # do pipeline.yaml
    agents: list[str]           # agentes alocados
    status: str                 # pending, running, checkpoint, completed, failed
    agent_tasks: dict[str, asyncio.Task]
    agent_status: dict[str, str]  # agent → running/done/error
    started_at: float
    completed_at: float | None = None
    quality_gate_result: str | None = None  # passed/failed/skipped
    retries: int = 0

# Indexação:
_step_executions: dict[tuple[str, str], StepExecution]  # (demand_id, step_id) → exec
```

### D9. Presets como templates copiáveis

```
src/presets/
├── dev-openspec/
│   ├── pipeline/
│   │   ├── pipeline.yaml
│   │   └── steps/
│   │       ├── step-01-spec.md
│   │       ├── step-02-dev.md
│   │       ├── step-03-review.md
│   │       └── step-04-qa.md
│   └── agents/
│       ├── po/AGENTS.md
│       ├── dev-backend/AGENTS.md
│       ├── code-review/AGENTS.md
│       └── qa/AGENTS.md
├── infra-monitor/
│   ├── pipeline/...
│   └── agents/...
└── content-squad/
    ├── pipeline/...
    └── agents/...
```

`ai-dev-team create --preset dev-openspec` copia o template para `~/.ai-dev-team/teams/{nome}/`.

## Interfaces Principais

### PipelineLoader

```python
class PipelineLoader:
    """Carrega e parseia pipeline.yaml e step files."""
    def load(self, pipeline_dir: Path) -> PipelineConfig
    def load_step(self, step_file: Path) -> StepConfig
    def get_quality_gate(self, step: StepConfig) -> list[QualityCheck]
```

### PipelineExecutor

```python
class PipelineExecutor:
    """Avança pipeline automaticamente entre steps."""
    def get_current_step(self, demand_id: str) -> StepConfig | None
    def advance(self, demand_id: str) -> StepConfig | None
    def skip_step(self, demand_id: str, step_id: str) -> bool
    def rerun_step(self, demand_id: str, step_id: str) -> bool
    def get_state(self, demand_id: str) -> PipelineState
    def format_state_for_prompt(self, demand_id: str) -> str
```

### QualityGateEvaluator

```python
class QualityGateEvaluator:
    """Avalia quality gates de um step."""
    def evaluate(self, step: StepConfig, workspace: Path, result: str) -> VerificationResult
    def _check_file_exists(self, path: str, workspace: Path) -> bool
    def _check_structural(self, check: str, workspace: Path) -> bool | None
    async def _check_semantic(self, check: str, result: str) -> bool
```

## Fluxo de Execução

```
1. Usuário envia mensagem
2. Engine → run_squad_lead()
3. Squad Lead recebe:
   - Pipeline state completo (steps, status, quality gates)
   - Agentes disponíveis com allocation status
   - Histórico, lições, notas diárias (como hoje)
4. Squad Lead decide:
   a) Responder diretamente (pergunta simples)
   b) start_agent → engine avança step automaticamente
   c) advance_step / skip_step / rerun_step (override)
5. Agente conclui → engine avalia quality gate do step
6. Se quality gate passa → engine avança para próximo step
7. Se quality gate falha → engine re-tenta (até max_retries)
8. Se próximo step é checkpoint → engine pausa, notifica usuário
9. Quando pipeline completa → engine marca demand como done
```
