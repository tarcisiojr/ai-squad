# ai-squad

Plataforma de orquestração multi-agente por IA. Define times de agentes especializados com pipeline declarativo — framework-agnostic, funciona para desenvolvimento de software, infra, conteúdo ou qualquer domínio.

Você interage via **Telegram** (texto ou voz). Os agentes trabalham de forma autônoma, solicitando intervenção humana apenas em checkpoints do pipeline.

## Quick Start

```bash
# Instalar
pip install -e ".[dev]"

# Criar um time apontando para seu repositório
ai-squad create meu-time --repo ~/projetos/minha-api

# Preencher os tokens no .env gerado
# ~/.ai-squad/teams/meu-time/.env

# Iniciar o time (sobe container Docker)
ai-squad start meu-time
```

## Como Funciona

```
Você (Telegram)                    ai-squad (Docker)
     │                                    │
     │  "Criar API de autenticação"       │
     │───────────────────────────────────▶│
     │                                    │
     │                    ┌───────────────┴───────────────┐
     │                    │        Squad Lead             │
     │                    │  (lê pipeline, coordena)      │
     │                    └───────┬───────────────────────┘
     │                            │
     │                    Pipeline: step-by-step
     │                    ┌───────▼───────┐
     │  📋 "Aprovar?"     │  Step 1: PO   │
     │◀──────────────────│  (checkpoint) │
     │  ✅ Aprovar        └───────┬───────┘
     │───────────────────────────▶│
     │                    ┌───────▼───────┐
     │                    │  Step 2: Dev  │
     │                    │  (background) │
     │                    └───────┬───────┘
     │                    ┌───────▼───────┐
     │  🔍 "Aprovar?"     │  Step 3: Review│
     │◀──────────────────│  (checkpoint)  │
     │  ✅ Aprovar        └───────┬────────┘
     │───────────────────────────▶│
     │                    ┌───────▼───────┐
     │  ✅ "Concluído!"   │  Step 4: QA   │
     │◀──────────────────└───────────────┘
```

## Pipeline Declarativo

O fluxo de trabalho é definido em YAML, não em código. Cada time tem seu `pipeline/pipeline.yaml`:

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
      on_reject: implementacao
      max_review_cycles: 3
      file: steps/step-03-review.md

    - id: qualidade
      agent: qa
      file: steps/step-04-qa.md
```

```yaml
# Time de infra (sem OpenSpec, sem PO)
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

Cada step file define instruções, inputs, outputs e **quality gates**:

```markdown
## Quality Gate
- [ ] proposal.md existe e tem mais de 50 bytes
- [ ] tasks.md tem pelo menos 3 itens
- [ ] Cada spec tem critérios de aceite
```

## Presets

Times podem ser criados a partir de presets pré-configurados:

- **dev-openspec** — PO → Dev → Code Review → QA (desenvolvimento orientado a spec)
- **infra-monitor** — Triager → SRE → Validator (monitoramento e incidentes)

## Gerenciamento de Times

```bash
ai-squad create backend  --repo ~/projetos/api
ai-squad create frontend --repo ~/projetos/web

ai-squad list              # ver todos os times
ai-squad start --all       # iniciar todos
ai-squad stop frontend     # parar um time
ai-squad logs backend      # ver logs
ai-squad status backend    # ver demandas ativas
ai-squad build             # reconstruir imagem Docker
```

## Configuração

Ao criar um time, arquivos são gerados em `~/.ai-squad/teams/<nome>/`:

### `.env` — Tokens

```env
CLAUDE_CODE_OAUTH_TOKEN=seu-oauth-token
GITHUB_TOKEN=ghp_xxxxx
TELEGRAM_TOKEN=bot-token-do-botfather
TELEGRAM_CHAT_ID=seu-chat-id
```

### `config.yaml` — Configuração do time

```yaml
ai_provider: claude-agent-sdk
messaging_provider: telegram
agent_timeout: 300
ai_model: claude-sonnet-4-20250514

# Model routing (opcional)
# light_model: claude-haiku-4-5-20251001
# heavy_model: claude-sonnet-4-20250514

agents:
  po:
    name: "PO Agent"
    avatar: "📋"
    role: spec
  dev-backend:
    name: "Dev Backend"
    avatar: "⚙️"
    role: dev
    timeout: 600
```

## Arquitetura

```
src/
├── models.py                  # AgentStatus enum
├── factory.py                 # PlatformConfig + AgentConfig (DI)
├── daemon.py                  # Loop principal: Telegram + heartbeat
├── messaging/
│   ├── interface.py           # ABC MessageBus
│   ├── cli.py                 # CLIMessageBus
│   └── telegram.py            # TelegramMessageBus (voz, fotos)
├── adapters/
│   ├── interface.py           # ABC AIAgentAdapter
│   └── claude_agent_sdk.py    # Claude Agent SDK + MCP tools
├── orchestrator/
│   ├── engine.py              # Squad Lead + delegação async
│   ├── pipeline.py            # Parser de pipeline.yaml e step files
│   ├── pipeline_state.py      # Estado e executor de pipeline
│   ├── verification.py        # Validação de artefatos
│   ├── prompt_builder.py      # Montagem de contexto para prompts
│   ├── media.py               # Detecção e envio de imagens
│   ├── model_router.py        # Roteamento light/heavy por complexidade
│   ├── atomic_write.py        # Escrita atômica (temp + fsync + rename)
│   ├── state.py               # Persistência JSON
│   ├── journal.py             # Decisões do Squad Lead
│   ├── conversation.py        # Histórico + sumarização automática
│   ├── lessons.py             # Aprendizado FTS5 entre demandas
│   ├── daily_notes.py         # Resumo diário para continuidade
│   ├── context.py             # Contexto do produto (CLAUDE.md + tree)
│   └── tools.py               # Modelos: RunningAgent, VerificationResult
├── presets/
│   ├── dev-openspec/          # Pipeline + agents para dev com OpenSpec
│   └── infra-monitor/         # Pipeline + agents para infra
└── whisper/                   # Transcrição de áudio
```

## MCP Tools

O Squad Lead e agentes têm acesso a estas tools:

| Tool | Descrição |
|------|-----------|
| `start_agent(name, task)` | Delega trabalho a um agente |
| `get_running_agents()` | Status dos agentes em background |
| `get_pipeline_state()` | Estado completo do pipeline |
| `advance_step()` | Avançar manualmente no pipeline |
| `skip_step(step_id)` | Pular um step |
| `rerun_step(step_id)` | Re-executar um step |
| `check_artifacts(name)` | Validar artefatos de uma change |
| `get_demand_state()` | Estado das demandas ativas |
| `read_journal()` | Histórico de decisões |
| `report_progress(msg)` | Feedback ao usuário |
| `send_image(path, caption)` | Enviar imagem via Telegram |
| `learn_lesson(cat, prob, sol)` | Registrar lição aprendida |

## Inteligência

- **Sumarização automática** — conversas longas (>20 msgs) são sumarizadas via LLM
- **Model routing** — mensagens simples usam modelo leve, complexas usam modelo capaz
- **Notas diárias** — últimos 3 dias injetados no prompt para continuidade
- **Lessons learned** — erros passados indexados via FTS5 e injetados nos prompts
- **Retry com backoff** — erros transientes retentados com backoff 2/4/8s
- **Monitor** — respostas vazias consecutivas resetam sessão do Squad Lead

## Desenvolvimento

```bash
source .venv/bin/activate
pip install -e ".[dev]"

# Testes (430+ testes)
python -m pytest tests/ -v

# Lint
ruff check src/
ruff format src/

# Type checking
pyright src/
```

## Extensibilidade

### Novo provider de IA
1. Criar classe herdando `AIAgentAdapter` em `src/adapters/`
2. Registrar: `factory.register_ai_adapter("nome", Classe)`
3. `config.yaml`: `ai_provider: nome`

### Novo canal de mensageria
1. Criar classe herdando `MessageBus` em `src/messaging/`
2. Registrar: `factory.register_message_bus("nome", Classe)`
3. `config.yaml`: `messaging_provider: nome`

### Novo pipeline/preset
1. Criar `src/presets/<nome>/` com `pipeline/` e `agents/`
2. Definir `pipeline.yaml` com steps
3. Criar step files com quality gates
4. Criar `AGENTS.md` para cada agente

## Requisitos

- Python 3.11+
- Docker
- Conta Claude Code com OAuth token
- Bot Telegram (via [@BotFather](https://t.me/BotFather))
- GitHub token (para criação de PRs)

## Licença

Este projeto é de uso privado.
