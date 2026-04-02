# AI Squad

Plataforma de orquestração multi-agente por IA com pipeline declarativo framework-agnostic. Agentes especializados executam steps definidos em YAML, com quality gates e checkpoints para aprovação humana.

## Visão Geral

O usuário interage via messaging (Telegram ou CLI). O Squad Lead coordena o time lendo o pipeline e delegando trabalho. Agentes trabalham de forma autônoma e só pausam em checkpoints.

## Arquitetura

Monorepo Python 3.11+ com módulos desacoplados via interfaces ABC. Pipeline declarativo em YAML define o fluxo de trabalho — o engine é agnóstico ao domínio.

```
ai-squad/
├── ai_squad/
│   ├── models.py              # Enum: AgentStatus
│   ├── factory.py             # PlatformConfig + AgentConfig (DI)
│   ├── daemon.py              # Loop principal: Telegram polling + heartbeat
│   ├── path_resolver.py       # Resolução de caminhos (local vs docker)
│   ├── messaging/
│   │   ├── interface.py       # ABC MessageBus
│   │   ├── cli.py             # CLIMessageBus (stdin/stdout)
│   │   └── telegram.py        # TelegramMessageBus (voz, fotos, markdown)
│   ├── adapters/
│   │   ├── interface.py       # ABC AIAgentAdapter (+ callbacks opcionais)
│   │   ├── claude_agent_sdk.py # Claude Agent SDK com subagentes nativos
│   │   ├── copilot_adapter.py # GitHub Copilot SDK com tools in-process
│   │   ├── agno_adapter.py    # Agno (Google Gemini) com toolkits
│   │   ├── mcp_tools_server.py # Tools de orquestração (callbacks do engine)
│   │   └── prompt_builder.py  # Montagem de prompt compartilhada
│   ├── orchestrator/
│   │   ├── engine.py          # Squad Lead hub-spoke + delegação async
│   │   ├── agent_runner.py    # Gerencia agentes em background (asyncio tasks)
│   │   ├── pipeline.py        # Parser de pipeline.yaml e step files
│   │   ├── pipeline_state.py  # Estado e executor de pipeline
│   │   ├── prompt_builder.py  # Montagem de contexto para prompts
│   │   ├── media.py           # Detecção e envio de imagens/arquivos
│   │   ├── model_router.py    # Roteamento de modelo por complexidade/tier
│   │   ├── atomic_write.py    # Escrita atômica compartilhada (fsync)
│   │   ├── state.py           # Persistência JSON de estado
│   │   ├── journal.py         # Decisões do Squad Lead por demanda
│   │   ├── conversation.py    # Histórico de conversa + sumarização
│   │   ├── lessons.py         # Aprendizado FTS5 entre demandas
│   │   ├── daily_notes.py     # Notas diárias para continuidade
│   │   ├── context.py         # WorkspaceContextCollector (CLAUDE.md + tree)
│   │   └── tools.py           # Modelo: RunningAgent
│   ├── presets/               # Pipelines pré-configurados
│   │   ├── dev-openspec/      # PO → Dev → Review → QA
│   │   └── infra-monitor/     # Triager → SRE → Validator
│   ├── cli/                   # CLI: create, start, stop, list, status
│   │   ├── main.py
│   │   ├── team_manager.py
│   │   └── templates/config.py
│   └── whisper/               # Transcrição de áudio (Whisper, Docker only)
├── tests/                     # Testes espelhando estrutura do ai_squad/
└── openspec/                  # Artefatos OpenSpec do próprio projeto
```

## Modos de Execução

### Modo Local (default)
```bash
cd ~/Projetos/minha-app
ai-squad create MeuTime          # cria .ai-squad/ no diretório corrente
nano .ai-squad/.env               # preenche tokens
ai-squad start MeuTime            # foreground, Ctrl+C para parar
```

### Modo Docker (opt-in)
```bash
ai-squad create MeuTime --repo ~/app   # cria em ~/.ai-squad/teams/
nano ~/.ai-squad/teams/MeuTime/.env
ai-squad start MeuTime                  # detecta Docker, sobe container
```

O `PathResolver` centraliza a resolução de caminhos — modo local usa `.ai-squad/` relativo ao projeto, modo Docker usa `/workspace`, `/app/*`.

## Decisões de Design

- **Pipeline declarativo** — fluxo de trabalho definido em YAML (pipeline.yaml), step files contêm apenas conteúdo (quality gates, veto conditions). Configuração vem exclusivamente do pipeline.yaml
- **Quality gates híbridos** — verificações de arquivo/estrutura resolvidas em código, semânticas via LLM
- **Modelo C (auto + override)** — pipeline avança automaticamente entre steps; Squad Lead pode override via skip/rerun/advance
- **Presets como templates** — `dev-openspec`, `infra-monitor` são diretórios copiáveis com pipeline + agents prontos
- **Módulos independentes, não microserviços** — desacoplamento via ABC sem overhead de comunicação inter-serviços
- **Factory pattern** — `PlatformFactory` é o único ponto que conhece implementações concretas
- **Callbacks opcionais na interface** — `AIAgentAdapter` define callbacks como no-op, adapter concreto sobrescreve
- **Tools in-process (Copilot)** — tools registradas via `define_tool()` no mesmo processo, sem subprocess MCP. Cada agente tem session isolada (`agent_name--demand_id`)
- **Token obrigatório por provider** — mapeamento centralizado em `_PROVIDER_AI_TOKENS` (factory.py). Copilot não requer token (auth via CLI), Agno requer `GOOGLE_API_KEY`
- **PathResolver** — resolução dinâmica de caminhos (local vs docker), daemon é agnóstico ao ambiente
- **Model routing por tier** — pipeline define `model_tier` (fast/powerful) por step, config mapeia para modelos concretos
- **Escrita atômica com fsync** — `atomic_write.py` compartilhado por state, journal, conversation, daily_notes
- **Sumarização automática** — quando conversa excede 20 mensagens, sumariza as antigas via LLM
- **Notas diárias** — resumo do que foi feito por dia, últimos 3 dias injetados no prompt
- **Retry com backoff** — erros transientes retentados com backoff 2/4/8s; context_length_exceeded comprime prompt
- **Respostas conversacionais no Telegram** — agentes nunca expõem raciocínio interno nem dados de orquestração

## Pipeline e Steps

O fluxo é definido em `pipeline/pipeline.yaml` (fonte única de configuração). Cada step referencia um `.md` com:

- **Quality Gate** — checklist de verificação (arquivo/estrutural/semântico)
- **Veto Conditions** — condições que reprovam automaticamente

Campos de configuração do step (no pipeline.yaml):
- `type` — `agent` (avança auto) ou `checkpoint` (pausa para aprovação humana)
- `execution` — `subagent` (aguarda), `background` (paralelo) ou `inline`
- `model_tier` — `fast` ou `powerful` (mapeado para light_model/heavy_model do config)
- `on_reject` — step_id para loop de revisão

## Interfaces Principais

### MessageBus (ai_squad/messaging/interface.py)
- `send_message(user_id, text, **kwargs)` — envia texto
- `send_photo(user_id, photo_path, caption)` — envia imagem
- `send_approval_request(user_id, question, options) → str` — aprovação
- `ask_user(user_id, question) → str` — pergunta texto livre
- `send_typing(user_id)` — indicador de digitação
- `notify(user_id, text)` — notificação

### AIAgentAdapter (ai_squad/adapters/interface.py)
- `run(prompt, context) → str` — executa agente
- `ask(question) → str` — pergunta simples
- `status() → AgentStatus` — status atual
- `on_human_needed(callback)` — callback para intervenção humana
- `set_*_callback(fn)` — callbacks opcionais (progress, start_agent, send_image, etc.)

## Configuração

Centralizada em `config.yaml` (dentro de `.ai-squad/` local ou `~/.ai-squad/teams/<nome>/` Docker):

```yaml
# Providers de IA: claude-agent-sdk (default), copilot, agno
ai_provider: claude-agent-sdk
messaging_provider: telegram
ai_model: claude-sonnet-4-20250514

# activation_mode: mention (default), all, command
# Em modo fórum do Telegram, "mention" exige @bot para ativar tópico
# "all" processa toda mensagem sem precisar de menção

# Model routing por tier (opcional)
# light_model: claude-haiku-4-5-20251001
# heavy_model: claude-sonnet-4-20250514

agent_timeout: 300

squad_lead:
  name: "Squad Lead"
  avatar: "👨‍💼"

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
1. Criar classe herdando `AIAgentAdapter` em `ai_squad/adapters/`
2. Implementar métodos abstratos + sobrescrever callbacks desejados
3. Registrar no `daemon.py` (`_create_<nome>_adapter`) e no mapeamento `creators`
4. Adicionar token obrigatório em `_PROVIDER_AI_TOKENS` (factory.py) — vazio = sem token
5. Adicionar template de `.env` em `ai_squad/cli/templates/config.py` se necessário
6. `config.yaml`: `ai_provider: nome`

Providers disponíveis:
- **claude-agent-sdk** — Claude com subagentes nativos e MCP tools (default)
- **copilot** — GitHub Copilot SDK com tools in-process via `define_tool()`. Auth via `copilot auth login` (sem token obrigatório). Instalar com `pip install -e '.[copilot]'`
- **agno** — Google Gemini via Agno SDK com toolkits (web_search, code_execution, shell). Requer `GOOGLE_API_KEY`

### Novo canal de mensageria
1. Criar classe herdando `MessageBus` em `ai_squad/messaging/`
2. `config.yaml`: `messaging_provider: nome`

### Novo agente
1. Criar `AGENTS.md` no diretório do agente (no preset ou no time)
2. Adicionar no `config.yaml` do time (seção agents)
3. Referenciar no `pipeline.yaml` do step correspondente

### Novo pipeline/preset
1. Criar `ai_squad/presets/<nome>/` com `pipeline/` e `agents/`
2. Definir `pipeline.yaml` com steps (fonte única de configuração)
3. Criar step files `.md` com quality gates (sem frontmatter)
4. `ai-squad create MeuTime --preset <nome>`

## Comandos

```bash
# Modo local
ai-squad create MeuTime              # cria .ai-squad/ no cwd
ai-squad start MeuTime               # foreground (Ctrl+C para parar)
ai-squad start MeuTime --local       # força modo local

# Modo Docker
ai-squad create MeuTime --repo ~/app # cria em ~/.ai-squad/teams/
ai-squad start MeuTime --docker      # força modo Docker
ai-squad stop MeuTime                # para container
ai-squad build                       # reconstrói imagem

# Gestão
ai-squad list                        # lista todos os times
ai-squad status MeuTime              # status de demandas
ai-squad remove MeuTime              # remove time
ai-squad add-agent MeuTime sec       # adiciona agente
ai-squad remove-agent MeuTime sec    # remove agente
ai-squad list-agents MeuTime         # lista agentes
```

## Desenvolvimento

```bash
source .venv/bin/activate

# Testes (400+)
python -m pytest tests/ -v

# Lint + format
ruff check ai_squad/ && ruff format ai_squad/

# Type checking
pyright ai_squad/
```
