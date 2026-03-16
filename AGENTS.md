# AI Dev Platform

Plataforma de desenvolvimento autônomo por IA com agentes especializados (PO, Dev Backend, Dev Frontend, Code Review, QA) que orquestram o ciclo completo de entrega — da demanda à produção.

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
│   ├── factory.py             # PlatformConfig + AgentConfig + SubmoduleConfig (DI)
│   ├── daemon.py              # Loop principal: Telegram polling + heartbeat
│   ├── barramento/
│   │   ├── interface.py       # ABC MessageBus
│   │   ├── cli.py             # CLIMessageBus (stdin/stdout)
│   │   └── telegram.py        # TelegramMessageBus (voz, fotos, markdown)
│   ├── adapters/
│   │   ├── interface.py       # ABC AIAgentAdapter
│   │   └── claude_agent_sdk.py # Claude Agent SDK com MCP tools
│   ├── orchestrator/
│   │   ├── engine.py          # Squad Lead hub-spoke + delegação async
│   │   ├── state.py           # Persistência JSON com escrita atômica
│   │   ├── journal.py         # Decisões e estado por demanda
│   │   ├── conversation.py    # Histórico de conversa (sobrevive restart)
│   │   ├── lessons.py         # Aprendizado entre demandas
│   │   ├── context.py         # Contexto do produto (CLAUDE.md + submodulos)
│   │   └── tools.py           # Modelos: RunningAgent, VerificationResult
│   └── whisper/
│       ├── server.py          # Serviço HTTP de transcrição de áudio
│       └── Dockerfile         # Container dedicado para Whisper
├── agents/                    # Personas com AGENTS.md + symlinks CLAUDE.md
│   ├── squad-lead/            # Coordenador do time
│   ├── po/                    # Product Owner (openspec)
│   ├── dev-backend/           # Desenvolvedor backend
│   ├── dev-frontend/          # Desenvolvedor frontend
│   ├── code-review/           # Revisor de código
│   └── qa/                    # Quality Assurance
├── .claude/docs/              # Documentos de referência detalhados
│   └── inteligencia.md        # Arquitetura de inteligência
├── state/                     # Estado persistido (JSON)
└── tests/                     # Testes, cobertura ≥ 80%
```

## Decisões de Design

- **Módulos independentes, não microserviços** — desacoplamento via ABC sem overhead de comunicação inter-serviços
- **Factory pattern** — `PlatformFactory` é o único ponto que conhece implementações concretas
- **Subprocess para Claude Code** — `claude --print` aproveita assinatura existente sem API key
- **JSON para estado** — simplicidade para v1, escrita atômica (temp + rename) previne corrupção
- **Docker para isolamento** — agentes executam em containers read-only com rede desabilitada
- **AGENTS.md como fonte única** — CLAUDE.md, GEMINI.md etc. são symlinks para AGENTS.md
- **Respostas conversacionais no Telegram** — agentes nunca expõem raciocínio interno (classificações, labels de intent, passos numerados). O usuário quer conversa natural, não debug <!-- Aprendido em: 2026-03-15 -->
- **Dockerfile: user agent para runtime** — dependências de sistema (apt, install-deps) rodam como root, mas browsers do Playwright e outros artefatos de runtime devem ser instalados APÓS `USER agent` para ficarem acessíveis ao processo <!-- Aprendido em: 2026-03-15 -->

## Ciclo de Vida de uma Demanda

```
PO (openspec) → Dev Backend + Dev Frontend (paralelo) → Code Review → QA
                        ↑                                    |
                        └──── (se REJEITADO) ────────────────┘
```

Squad Lead coordena o fluxo, delega via `start_agent` e verifica artefatos antes de cada transição. Detalhes da arquitetura de inteligência em `.claude/docs/inteligencia.md`.

## Interfaces Principais

### MessageBus (src/barramento/interface.py)
- `send_message(user_id, text)` — envia texto (Telegram: `parse_mode="Markdown"` com fallback para texto plano)
- `send_photo(user_id, photo_path, caption)` — envia imagem (Telegram only)
- `send_approval_request(user_id, question, options) → str` — pedido de aprovação
- `receive_message(callback)` — registra listener de texto
- `receive_voice(callback)` — registra listener de voz
- `notify(user_id, text)` — notificação

O engine detecta automaticamente caminhos de imagem e `.md` nas respostas dos agentes e envia como foto ou conteúdo inline no Telegram <!-- Aprendido em: 2026-03-15 -->

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

Cada agente pode ter timeout e submodules específicos:

```yaml
agents:
  dev-backend:
    name: "Dev Backend"
    avatar: "⚙️"
    timeout: 600
    submodules:
      - path: "packages/api"
        description: "API REST"
```

Para trocar provider, altere apenas `platform.yaml` — zero mudanças no código.

## CLI ai-dev-team

```bash
# Instalar CLI
pip install -e .

# Criar um novo time de desenvolvimento
ai-dev-team create backend-api --repo ~/projetos/minha-api

# Editar tokens no .env gerado
# ~/.ai-dev-team/teams/backend-api/.env

# Iniciar o time (sobe container Docker)
ai-dev-team start backend-api

# Listar todos os times
ai-dev-team list

# Ver logs do time
ai-dev-team logs backend-api

# Ver demandas ativas
ai-dev-team status backend-api

# Parar o time
ai-dev-team stop backend-api

# Reconstruir imagem Docker
ai-dev-team build
```

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
3. Adicionar entrada no `config.yaml` do time (agents section)
4. Nenhuma alteração de código necessária — verificação é dinâmica pelo conteúdo do AGENTS.md

### MCP Tools disponíveis para agentes
- `start_agent(agent_name, task_description)` — delega trabalho
- `get_running_agents()` — status dos agentes em background
- `check_artifacts(change_name)` — valida artefatos openspec
- `get_demand_state()` — estado das demandas ativas
- `read_journal()` — histórico de decisões
- `report_progress(message)` — feedback ao usuário
- `send_image(image_path, caption)` — envia foto no Telegram
- `learn_lesson(category, problem, solution)` — registra lição aprendida

### Inteligência e memória
- Lições aprendidas, monitor do Squad Lead, histórico de conversa, verificação dinâmica — detalhes em `.claude/docs/inteligencia.md`
