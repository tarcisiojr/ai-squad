# ai-dev-team

Time completo de desenvolvimento autônomo por IA. Orquestra agentes especializados — **PO**, **Dev** e **QA** — para conduzir o ciclo completo de entrega de software, da demanda à produção.

Você interage via **Telegram** (texto ou voz). Os agentes trabalham de forma autônoma, solicitando intervenção humana apenas em pontos de decisão: aprovação de plano, aprovação de PR e erros bloqueantes.

## Quick Start

```bash
# Instalar
pip install -e .

# Criar um time apontando para seu repositório
ai-dev-team create meu-time --repo ~/projetos/minha-api

# Preencher os tokens no .env gerado
# ~/.ai-dev-team/teams/meu-time/.env

# Iniciar o time (sobe container Docker em loop)
ai-dev-team start meu-time
```

Pronto. O bot do Telegram começa a escutar. Envie uma mensagem para criar uma demanda.

## Como Funciona

```
Você (Telegram)                    ai-dev-team (Docker)
     │                                    │
     │  "Criar API de autenticação"       │
     │───────────────────────────────────▶│
     │                                    │
     │                             ┌──────┴──────┐
     │                             │  PO Agent   │
     │  📋 "Aprovar plano?"        │  especifica │
     │◀────────────────────────────│             │
     │  ✅ Aprovar                  └──────┬──────┘
     │───────────────────────────────────▶│
     │                             ┌──────┴──────┐
     │                             │  Dev Agent  │
     │                             │  implementa │
     │                             │  commit/push│
     │  🔧 "Aprovar PR #42?"       │  cria PR    │
     │◀────────────────────────────│             │
     │  ✅ Aprovar                  └──────┬──────┘
     │───────────────────────────────────▶│
     │                             ┌──────┴──────┐
     │                             │  QA Agent   │
     │  ✅ "Demanda concluída!"     │  valida     │
     │◀────────────────────────────└─────────────┘
```

## Gerenciamento de Times

Cada time é uma instância independente: bot Telegram próprio, container Docker próprio, repositório alvo próprio.

```bash
# Criar múltiplos times
ai-dev-team create backend  --repo ~/projetos/api
ai-dev-team create frontend --repo ~/projetos/web
ai-dev-team create infra    --repo ~/projetos/terraform

# Gerenciar
ai-dev-team list                  # ver todos os times e status
ai-dev-team start --all           # iniciar todos
ai-dev-team stop frontend         # parar um time específico
ai-dev-team logs backend          # ver logs em tempo real
ai-dev-team status backend        # ver demandas ativas
ai-dev-team build                 # reconstruir imagem Docker
```

## Configuração

Ao criar um time, três arquivos são gerados em `~/.ai-dev-team/teams/<nome>/`:

### `.env` — Tokens obrigatórios

```env
CLAUDE_CODE_OAUTH_TOKEN=seu-oauth-token
GITHUB_TOKEN=ghp_xxxxx
TELEGRAM_TOKEN=bot-token-do-botfather
TELEGRAM_CHAT_ID=seu-chat-id

# Opcional (transcrição de voz)
# OPENAI_API_KEY=sk-xxxxx
```

### `config.yaml` — Configuração do time

```yaml
ai_provider: claude-code
messaging_provider: telegram
agent_timeout: 300
repo_path: /caminho/do/seu/repo
personas:
  po:
    name: "PO Agent"
    avatar: "📋"
  dev-orchestrator:
    name: "Dev Orchestrator"
    avatar: "🔧"
  qa:
    name: "QA Agent"
    avatar: "🧪"
```

### `docker-compose.yml` — Container do time

Gerado automaticamente. O container inclui Python, Node.js, Claude CLI, git, gh CLI e Docker CLI. O `docker.sock` do host é montado para que agentes possam subir infraestrutura do projeto (banco, Redis, etc.).

## Requisitos

- Python 3.11+
- Docker
- Conta Claude Code com OAuth token
- Bot Telegram (criado via [@BotFather](https://t.me/BotFather))
- GitHub token (para criação de PRs)

## Ciclo de Vida de uma Demanda

```
idle → po_working → awaiting_plan_approval → dev_working
     → awaiting_pr_approval → ci_running → qa_validating → done
```

| Estado | Descrição |
|--------|-----------|
| `idle` | Demanda recebida, aguardando processamento |
| `po_working` | PO elaborando especificação |
| `awaiting_plan_approval` | Aguardando aprovação humana do plano |
| `dev_working` | Dev implementando em worktree isolado |
| `awaiting_pr_approval` | Aguardando aprovação humana do PR |
| `ci_running` | Pipeline de CI executando |
| `qa_validating` | QA validando contra critérios de aceitação |
| `done` | Demanda concluída |

## Arquitetura

```
~/.ai-dev-team/
├── teams/
│   ├── backend/                  # Time 1
│   │   ├── config.yaml
│   │   ├── .env
│   │   ├── docker-compose.yml
│   │   └── state/
│   └── frontend/                 # Time 2
│       └── ...

Dentro do container Docker:
├── Python 3.11 + Node.js 20
├── claude CLI (via npm)
├── git + gh CLI
├── docker CLI (via docker.sock)
└── /workspace (repo alvo montado)
```

### Decisões Técnicas

| Decisão | Motivo |
|---------|--------|
| Docker para empacotamento | Preserva ambiente do host, dependências reproduzíveis |
| docker.sock montado | Agentes podem subir infra do projeto (postgres, redis) |
| `CLAUDE_CODE_OAUTH_TOKEN` | Auth limpa para Claude CLI dentro do container |
| Um bot Telegram por time | Isolamento total entre times |
| Worktrees git | Agentes trabalham em branches isoladas sem conflitos |
| Factory + ABC | Providers plugáveis sem acoplamento |
| JSON para estado | Simplicidade; escrita atômica previne corrupção |

## Extensibilidade

### Novo provider de IA
1. Criar classe herdando `AIAgentAdapter` em `src/adapters/`
2. Registrar: `factory.register_ai_adapter("nome", Classe)`
3. Atualizar `config.yaml`: `ai_provider: nome`

### Novo canal de mensageria
1. Criar classe herdando `MessageBus` em `src/barramento/`
2. Registrar: `factory.register_message_bus("nome", Classe)`
3. Atualizar `config.yaml`: `messaging_provider: nome`

### Novo agente
1. Criar diretório `agents/<nome>/` com `AGENTS.md`
2. Symlink: `ln -sf AGENTS.md CLAUDE.md`
3. Adicionar em `registry.yaml`

## Desenvolvimento

```bash
source .venv/bin/activate
pip install -e ".[dev]"

# Testes (212 testes, cobertura ~88%)
python -m pytest tests/ -v

# Verificar cobertura mínima
python -m pytest tests/ --cov=src --cov-fail-under=80
```

## Licença

Este projeto é de uso privado.
