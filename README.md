# AI Dev Platform

Plataforma de desenvolvimento autônomo por IA que orquestra um time de agentes especializados — **PO**, **Dev** e **QA** — para conduzir o ciclo completo de entrega de software, da demanda à produção.

O usuário interage via barramento de mensagens (Telegram ou CLI). Os agentes trabalham de forma autônoma, solicitando intervenção humana apenas em pontos de decisão: aprovação de plano, aprovação de PR e erros bloqueantes.

## Principais Funcionalidades

- **Orquestração por máquina de estados** — ciclo de vida de demandas com transições controladas (`idle` → `po_working` → ... → `done`)
- **Providers plugáveis** — troque IA (Claude Code, Gemini, Copilot) ou mensageria (Telegram, Slack, CLI) alterando apenas `platform.yaml`
- **Registry de agentes** — catálogo YAML com matching automático por domínio e prioridade
- **Isolamento via Docker** — agentes executam em containers read-only, sem acesso ao host
- **Identidade por persona** — cada agente tem nome, avatar e token próprios no canal de mensageria
- **Transcrição de voz** — mensagens de áudio são transcritas automaticamente via Whisper API

## Requisitos

- Python 3.11+
- Docker (para isolamento de agentes)
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (provider de IA padrão)

## Instalação

```bash
# Clonar o repositório
git clone <url-do-repo>
cd ai-dev-platform

# Criar e ativar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependências
pip install -e ".[dev]"
```

## Configuração

Toda a configuração é centralizada em `platform.yaml`:

```yaml
ai_provider: claude-code         # Provider de IA
messaging_provider: cli           # Provider de mensageria
agent_timeout: 300                # Timeout por agente (segundos)
state_dir: state/                 # Diretório de persistência

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

Para usar Telegram, altere `messaging_provider: telegram` e adicione `token` em cada persona.

## Uso Rápido

```python
import asyncio
from src.factory import PlatformConfig, PlatformFactory
from src.barramento.cli import CLIMessageBus
from src.adapters.claude_code import ClaudeCodeAdapter
from src.orchestrator.engine import OrchestrationEngine
from src.orchestrator.state import StateManager

# Carregar configuração
config = PlatformConfig.from_yaml("platform.yaml")

# Montar componentes via factory
factory = PlatformFactory()
factory.register_message_bus("cli", CLIMessageBus)
factory.register_ai_adapter("claude-code", ClaudeCodeAdapter)

bus = factory.create_message_bus(config)
adapter = factory.create_ai_adapter(config)
state_mgr = StateManager(state_dir=config.state_dir)

# Criar engine e executar demanda
engine = OrchestrationEngine(adapter, bus, state_mgr)

asyncio.run(
    engine.run_demand_cycle("demand-001", "user1", "Criar API de autenticação")
)
```

## Estrutura do Projeto

```
├── platform.yaml              # Configuração de providers e personas
├── registry.yaml              # Catálogo de agentes por domínio
├── src/
│   ├── models.py              # Enums (AgentStatus, DemandState)
│   ├── factory.py             # PlatformConfig + PlatformFactory
│   ├── barramento/            # Implementações de MessageBus
│   ├── adapters/              # Implementações de AIAgentAdapter
│   ├── orchestrator/          # Engine, estado, worktrees, Docker
│   └── registry/              # AgentRegistry
├── agents/                    # Personas (PO, Dev, QA, dev-web)
├── specs/                     # Contratos (OpenAPI, AsyncAPI)
├── state/                     # Estado persistido (JSON)
└── tests/                     # 114 testes unitários e de integração
```

## Testes

```bash
# Rodar todos os testes com cobertura
python -m pytest tests/ -v

# Apenas testes de um módulo
python -m pytest tests/test_orchestrator.py -v

# Verificar cobertura mínima (80%)
python -m pytest tests/ --cov=src --cov-fail-under=80
```

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
| `dev_working` | Subagentes implementando em worktrees isolados |
| `awaiting_pr_approval` | Aguardando aprovação humana do PR |
| `ci_running` | Pipeline de CI executando |
| `qa_validating` | QA validando contra critérios de aceitação |
| `done` | Demanda concluída |

## Extensibilidade

### Adicionar novo provider de IA

1. Criar classe herdando `AIAgentAdapter` em `src/adapters/`
2. Registrar: `factory.register_ai_adapter("meu-provider", MinhaClasse)`
3. Atualizar `platform.yaml`: `ai_provider: meu-provider`

### Adicionar novo canal de mensageria

1. Criar classe herdando `MessageBus` em `src/barramento/`
2. Registrar: `factory.register_message_bus("meu-canal", MinhaClasse)`
3. Atualizar `platform.yaml`: `messaging_provider: meu-canal`

### Adicionar novo agente

1. Criar diretório `agents/<nome>/` com `AGENTS.md`
2. Criar symlink: `ln -sf AGENTS.md CLAUDE.md`
3. Adicionar entrada em `registry.yaml` com domínio e prioridade
4. Nenhuma alteração de código necessária

## Decisões Técnicas

| Decisão | Motivo |
|---------|--------|
| Módulos Python, não microserviços | Desacoplamento via ABC sem overhead de rede na v1 |
| Factory + injeção via construtor | Único ponto que conhece implementações concretas |
| `claude --print` via subprocess | Aproveita assinatura existente sem API key separada |
| JSON para estado | Simplicidade para v1; escrita atômica previne corrupção |
| Docker read-only + rede desabilitada | Isolamento de segurança para agentes executando código |
| AGENTS.md + symlinks | Fonte única de contexto agnóstica a provider de IA |

## Licença

Este projeto é de uso privado.
