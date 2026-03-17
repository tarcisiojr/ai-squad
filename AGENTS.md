# AI Dev Platform

Plataforma de orquestração multi-agente por IA com pipeline declarativo framework-agnostic. Agentes especializados executam steps definidos em YAML, com quality gates e checkpoints para aprovação humana.

## Visão Geral

O usuário interage via messaging (Telegram ou CLI). O Squad Lead coordena o time lendo o pipeline e delegando trabalho. Agentes trabalham de forma autônoma e só pausam em checkpoints.

## Arquitetura

Monorepo Python 3.11+ com módulos desacoplados via interfaces ABC. Pipeline declarativo em YAML define o fluxo de trabalho — o engine é agnóstico ao domínio.

```
ai-dev-platform/
├── platform.yaml              # Configuração centralizada (providers, timeouts)
├── src/
│   ├── models.py              # Enum: AgentStatus
│   ├── factory.py             # PlatformConfig + AgentConfig (DI)
│   ├── daemon.py              # Loop principal: Telegram polling + heartbeat
│   ├── messaging/
│   │   ├── interface.py       # ABC MessageBus
│   │   ├── cli.py             # CLIMessageBus (stdin/stdout)
│   │   └── telegram.py        # TelegramMessageBus (voz, fotos, markdown)
│   ├── adapters/
│   │   ├── interface.py       # ABC AIAgentAdapter
│   │   └── claude_agent_sdk.py # Claude Agent SDK com MCP tools
│   ├── orchestrator/
│   │   ├── engine.py          # Squad Lead hub-spoke + delegação async
│   │   ├── pipeline.py        # Parser de pipeline.yaml e step files
│   │   ├── pipeline_state.py  # Estado e executor de pipeline
│   │   ├── verification.py    # Validação de artefatos (OpenSpec e outros)
│   │   ├── prompt_builder.py  # Montagem de contexto para prompts
│   │   ├── media.py           # Detecção e envio de imagens/arquivos
│   │   ├── model_router.py    # Roteamento de modelo por complexidade
│   │   ├── atomic_write.py    # Escrita atômica compartilhada (fsync)
│   │   ├── state.py           # Persistência JSON de estado
│   │   ├── journal.py         # Decisões do Squad Lead por demanda
│   │   ├── conversation.py    # Histórico de conversa + sumarização
│   │   ├── lessons.py         # Aprendizado FTS5 entre demandas
│   │   ├── daily_notes.py     # Notas diárias para continuidade
│   │   ├── context.py         # Contexto do produto (CLAUDE.md + tree)
│   │   └── tools.py           # Modelos: RunningAgent, VerificationResult
│   ├── presets/               # Pipelines pré-configurados
│   │   ├── dev-openspec/      # PO → Dev → Review → QA
│   │   └── infra-monitor/     # Triager → SRE → Validator
│   └── whisper/               # Transcrição de áudio (Whisper)
├── tests/                     # Testes espelhando estrutura do src/
│   ├── adapters/
│   ├── messaging/
│   ├── cli/
│   └── orchestrator/
└── openspec/                  # Artefatos OpenSpec do próprio projeto
```

## Decisões de Design

- **Pipeline declarativo** — fluxo de trabalho definido em YAML (pipeline.yaml + step files), não em código Python. Engine é agnóstico ao domínio
- **Quality gates híbridos** — verificações de arquivo/estrutura resolvidas em código, semânticas via LLM. Declarados nos step files
- **Modelo C (auto + override)** — pipeline avança automaticamente entre steps; Squad Lead pode override via skip/rerun/advance
- **Presets como templates** — `dev-openspec`, `infra-monitor` são diretórios copiáveis com pipeline + agents prontos
- **Módulos independentes, não microserviços** — desacoplamento via ABC sem overhead de comunicação inter-serviços
- **Factory pattern** — `PlatformFactory` é o único ponto que conhece implementações concretas
- **Escrita atômica com fsync** — `atomic_write.py` compartilhado por state, journal, conversation, daily_notes
- **Sumarização automática** — quando conversa excede 20 mensagens, sumariza as antigas via LLM
- **Model routing por complexidade** — classifica mensagens como light/heavy e roteia para modelo apropriado
- **Notas diárias** — resumo do que foi feito por dia, últimos 3 dias injetados no prompt
- **Retry com backoff** — erros transientes retentados com backoff 2/4/8s; context_length_exceeded comprime prompt
- **Respostas conversacionais no Telegram** — agentes nunca expõem raciocínio interno. Conversa natural, não debug
- **Dockerfile: user agent para runtime** — dependências rodam como root, browsers do Playwright como `USER agent`

## Pipeline e Steps

O fluxo é definido em `pipeline/pipeline.yaml`. Cada step referencia um `.md` com:

- **Frontmatter YAML** — agent, type, execution, model_tier, on_reject
- **Quality Gate** — checklist de verificação (arquivo/estrutural/semântico)
- **Veto Conditions** — condições que reprovam automaticamente

Steps com `type: checkpoint` pausam para aprovação humana. Steps com `on_reject` criam loops de revisão (ex: review rejeita → volta pro dev → review re-avalia).

## Interfaces Principais

### MessageBus (src/messaging/interface.py)
- `send_message(user_id, text, **kwargs)` — envia texto
- `send_photo(user_id, photo_path, caption)` — envia imagem
- `send_approval_request(user_id, question, options) → str` — aprovação
- `ask_user(user_id, question) → str` — pergunta texto livre
- `send_typing(user_id)` — indicador de digitação
- `notify(user_id, text)` — notificação

### AIAgentAdapter (src/adapters/interface.py)
- `run(prompt, context) → str` — executa agente
- `ask(question) → str` — pergunta simples
- `status() → AgentStatus` — status atual
- `on_human_needed(callback)` — callback para intervenção humana

## Configuração

Centralizada em `platform.yaml`:

```yaml
ai_provider: claude-agent-sdk
messaging_provider: cli
ai_model: claude-sonnet-4-20250514

# Model routing (opcional)
# light_model: claude-haiku-4-5-20251001
# heavy_model: claude-sonnet-4-20250514

agent_timeout: 300
state_dir: state/

agents:
  po:
    name: "PO Agent"
    avatar: "📋"
    role: spec       # spec, dev, review, generic
  dev-backend:
    name: "Dev Backend"
    avatar: "⚙️"
    role: dev
    timeout: 600
```

## MCP Tools

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

## Extensibilidade

### Novo provider de IA
1. Criar classe herdando `AIAgentAdapter` em `src/adapters/`
2. Registrar: `factory.register_ai_adapter("nome", Classe)`
3. `platform.yaml`: `ai_provider: nome`

### Novo canal de mensageria
1. Criar classe herdando `MessageBus` em `src/messaging/`
2. Registrar: `factory.register_message_bus("nome", Classe)`
3. `platform.yaml`: `messaging_provider: nome`

### Novo agente
1. Criar `AGENTS.md` no diretório do agente (no preset ou no time)
2. Adicionar no `config.yaml` do time (seção agents)
3. Referenciar no `pipeline.yaml` do step correspondente

### Novo pipeline/preset
1. Criar `src/presets/<nome>/` com `pipeline/` e `agents/`
2. Definir `pipeline.yaml` com steps
3. Criar step files `.md` com quality gates
4. `ai-dev-team create --preset <nome> meu-time --repo ~/repo`

## Comandos de Desenvolvimento

```bash
source .venv/bin/activate

# Testes (430+)
python -m pytest tests/ -v

# Lint + format
ruff check src/ && ruff format src/

# Type checking
pyright src/
```
