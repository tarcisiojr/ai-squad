# ai-squad

Plataforma de orquestração multi-agente por IA. Define times de agentes especializados com pipeline declarativo — framework-agnostic, funciona para desenvolvimento de software, infra, análise de investimentos ou qualquer domínio.

Você interage via **Telegram** (texto ou voz). Os agentes trabalham de forma autônoma, solicitando intervenção humana apenas em checkpoints do pipeline.

## Instalação

```bash
# Instala globalmente via uv (recomendado)
uv tool install --editable .

# Mudanças no código refletem automaticamente (editable mode).
# Só precisa reinstalar se alterar dependências no pyproject.toml.
```

## Quick Start

### Modo Local (recomendado para começar)

```bash
cd ~/projetos/minha-api
ai-squad create meu-time              # cria .ai-squad/ no diretório corrente
nano .ai-squad/.env                    # preencher tokens
ai-squad start meu-time                # foreground, Ctrl+C para parar
```

### Modo Docker (produção/isolamento)

```bash
ai-squad create meu-time --repo ~/projetos/minha-api
nano ~/.ai-squad/teams/meu-time/.env
ai-squad start meu-time                # sobe container em background
```

## Como Funciona

```
Você (Telegram)                    ai-squad
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

O fluxo de trabalho é definido em YAML (fonte única de configuração). Step files contêm apenas conteúdo (quality gates, veto conditions):

```yaml
pipeline:
  steps:
    - id: especificacao
      agent: po
      type: checkpoint           # pausa para aprovação humana
      execution: subagent
      model_tier: powerful
      file: steps/step-01-spec.md

    - id: implementacao
      agents: [dev-backend, dev-frontend]
      type: agent                # avança automaticamente
      execution: background      # agentes em paralelo
      model_tier: powerful
      file: steps/step-02-dev.md

    - id: revisao
      agent: code-review
      type: checkpoint
      on_reject: implementacao   # loop de revisão
      max_review_cycles: 3
      file: steps/step-03-review.md

    - id: qualidade
      agent: qa
      type: agent
      model_tier: powerful
      file: steps/step-04-qa.md
```

## Presets

Times podem ser criados a partir de presets pré-configurados:

- **dev-openspec** — PO → Dev (backend+frontend) → Code Review → QA
- **infra-monitor** — Triager → SRE → Validator

## Comandos

```bash
# Criação
ai-squad create MeuTime              # modo local (.ai-squad/ no cwd)
ai-squad create MeuTime --repo ~/app # modo Docker (~/.ai-squad/teams/)

# Execução
ai-squad start MeuTime               # auto-detecta modo (local ou docker)
ai-squad start MeuTime --local       # força modo local
ai-squad start MeuTime --docker      # força modo Docker
ai-squad stop MeuTime                # para container Docker

# Gestão
ai-squad list                        # lista todos os times
ai-squad status MeuTime              # demandas ativas
ai-squad remove MeuTime              # remove time
ai-squad logs MeuTime                # logs do container

# Agentes
ai-squad add-agent MeuTime sec       # adiciona agente
ai-squad remove-agent MeuTime sec    # remove agente
ai-squad list-agents MeuTime         # lista agentes

# Docker
ai-squad build                       # reconstrói imagem
```

## Configuração

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
ai_model: claude-sonnet-4-20250514
agent_timeout: 300

# Model routing por tier (opcional)
# light_model: claude-haiku-4-5-20251001
# heavy_model: claude-sonnet-4-20250514

agents:
  po:
    name: "PO Agent"
    avatar: "📋"
    command: "/po"
  dev-backend:
    name: "Dev Backend"
    avatar: "⚙️"
    command: "/dev-back"
    timeout: 600
```

## Inteligência

- **Sumarização automática** — conversas longas (>20 msgs) são sumarizadas via LLM
- **Model routing** — pipeline define `model_tier` por step, config mapeia para modelos concretos
- **Notas diárias** — últimos 3 dias injetados no prompt para continuidade
- **Lessons learned** — erros passados indexados via FTS5 e injetados nos prompts
- **Retry com backoff** — erros transientes retentados com backoff 2/4/8s

## Desenvolvimento

```bash
source .venv/bin/activate
pip install -e ".[dev]"

# Testes (400+)
python -m pytest tests/ -v

# Lint
ruff check src/ && ruff format src/

# Type checking
pyright src/
```

## Extensibilidade

### Novo provider de IA
1. Criar classe herdando `AIAgentAdapter` em `src/adapters/`
2. Implementar métodos abstratos + sobrescrever callbacks desejados
3. `config.yaml`: `ai_provider: nome`

### Novo canal de mensageria
1. Criar classe herdando `MessageBus` em `src/messaging/`
2. `config.yaml`: `messaging_provider: nome`

### Novo pipeline/preset
1. Criar `src/presets/<nome>/` com `pipeline/` e `agents/`
2. Definir `pipeline.yaml` com steps (fonte única de configuração)
3. Criar step files com quality gates (sem frontmatter)
4. `ai-squad create MeuTime --preset <nome>`

## Requisitos

- Python 3.11+
- Docker (opcional, para modo isolado)
- Conta Claude Code com OAuth token
- Bot Telegram (via [@BotFather](https://t.me/BotFather))
- GitHub token (para criação de PRs)

## Licença

Este projeto é de uso privado.
