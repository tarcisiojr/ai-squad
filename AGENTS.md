# AI Dev Platform

Plataforma de desenvolvimento autônomo por IA com agentes especializados (PO, Dev, QA) que orquestram o ciclo completo de entrega — da demanda à produção.

## Visão Geral

O usuário interage exclusivamente via barramento de mensagens (Telegram ou CLI). Agentes trabalham de forma autônoma e só solicitam intervenção humana em pontos de decisão (aprovação de plano, aprovação de PR, erros bloqueantes).

## Arquitetura

Monorepo Python 3.11+ com módulos desacoplados via interfaces ABC. Nenhum componente importa implementações concretas — apenas a `PlatformFactory` conhece o mapeamento provider → implementação.

```
ai-dev-platform/
├── platform.yaml              # Configuração centralizada (providers, personas, timeouts)
├── registry.yaml              # Catálogo de agentes por domínio
├── src/
│   ├── models.py              # Enums: AgentStatus, DemandState, VALID_TRANSITIONS
│   ├── factory.py             # PlatformConfig + PlatformFactory (DI via construtor)
│   ├── barramento/
│   │   ├── interface.py       # ABC MessageBus
│   │   ├── cli.py             # CLIMessageBus (stdin/stdout)
│   │   └── telegram.py        # TelegramMessageBus (voz via Whisper)
│   ├── adapters/
│   │   ├── interface.py       # ABC AIAgentAdapter
│   │   └── claude_code.py     # ClaudeCodeAdapter (subprocess `claude --print`)
│   ├── orchestrator/
│   │   ├── engine.py          # Máquina de estados + despacho de agentes
│   │   ├── state.py           # Persistência JSON com escrita atômica
│   │   ├── worktree.py        # Gerenciamento de worktrees git por subagente
│   │   └── docker.py          # Execução isolada de agentes via Docker
│   └── registry/
│       └── registry.py        # AgentRegistry com matching por domínio
├── agents/                    # Personas com AGENTS.md + symlinks CLAUDE.md
│   ├── po/                    # Product Owner
│   ├── dev-orchestrator/      # Orquestrador de desenvolvimento
│   ├── qa/                    # Quality Assurance
│   └── dev-web/               # Subagente web (skills/, tools.yaml)
├── specs/                     # Submodulos git com contratos (OpenAPI, AsyncAPI)
├── state/                     # Estado persistido das demandas (JSON)
└── tests/                     # 114 testes, cobertura ≥ 80%
```

## Decisões de Design

- **Módulos independentes, não microserviços** — desacoplamento via ABC sem overhead de comunicação inter-serviços
- **Factory pattern** — `PlatformFactory` é o único ponto que conhece implementações concretas
- **Subprocess para Claude Code** — `claude --print` aproveita assinatura existente sem API key
- **JSON para estado** — simplicidade para v1, escrita atômica (temp + rename) previne corrupção
- **Docker para isolamento** — agentes executam em containers read-only com rede desabilitada
- **AGENTS.md como fonte única** — CLAUDE.md, GEMINI.md etc. são symlinks para AGENTS.md

## Ciclo de Vida de uma Demanda

```
idle → po_working → awaiting_plan_approval → dev_working
     → awaiting_pr_approval → ci_running → qa_validating → done
```

Transições controladas pela máquina de estados em `src/orchestrator/engine.py`. Transições inválidas levantam `InvalidTransitionError`.

## Interfaces Principais

### MessageBus (src/barramento/interface.py)
- `send_message(user_id, text)` — envia texto
- `send_approval_request(user_id, question, options) → str` — pedido de aprovação
- `receive_message(callback)` — registra listener de texto
- `receive_voice(callback)` — registra listener de voz
- `notify(user_id, text)` — notificação

### AIAgentAdapter (src/adapters/interface.py)
- `run(prompt, context) → str` — executa agente
- `ask(question) → str` — pergunta simples
- `status() → AgentStatus` — status atual
- `on_human_needed(callback)` — callback para intervenção humana

## Configuração

Tudo centralizado em `platform.yaml`:

```yaml
ai_provider: claude-code        # Provider de IA (plugável)
messaging_provider: cli          # Provider de mensageria (plugável)
agent_timeout: 300               # Timeout em segundos
state_dir: state/
personas:
  po:
    name: "PO Agent"
    avatar: "📋"
```

Para trocar provider, altere apenas `platform.yaml` — zero mudanças no código.

## Comandos de Desenvolvimento

```bash
# Ativar ambiente virtual
source .venv/bin/activate

# Rodar testes com cobertura
python -m pytest tests/ -v

# Verificar cobertura mínima (80%)
python -m pytest tests/ --cov=src --cov-fail-under=80
```

## Extensibilidade

### Novo provider de IA
1. Criar classe que herda `AIAgentAdapter` em `src/adapters/`
2. Registrar na factory: `factory.register_ai_adapter("nome", MinhaClasse)`
3. Atualizar `platform.yaml`: `ai_provider: nome`

### Novo provider de mensageria
1. Criar classe que herda `MessageBus` em `src/barramento/`
2. Registrar na factory: `factory.register_message_bus("nome", MinhaClasse)`
3. Atualizar `platform.yaml`: `messaging_provider: nome`

### Novo agente
1. Criar diretório `agents/<nome>/` com AGENTS.md
2. Criar symlink: `ln -sf AGENTS.md CLAUDE.md`
3. Adicionar entrada em `registry.yaml`
4. Nenhuma alteração de código necessária
