## Context

Projeto greenfield em Python 3.11+ para criar uma plataforma de desenvolvimento autônomo por IA. Não existe código anterior — tudo será construído do zero. A premissa central é o desacoplamento total entre componentes via interfaces ABC, permitindo troca de providers (IA e mensageria) sem alteração de código.

O usuário interage exclusivamente via barramento de mensagens. Agentes trabalham de forma autônoma e só solicitam intervenção humana em pontos de decisão (aprovação de plano, aprovação de PR, erros bloqueantes).

## Goals / Non-Goals

**Goals:**
- Arquitetura modular com componentes desacoplados via interfaces ABC
- Provider de IA plugável (Claude Code inicial, Gemini/Copilot futuros)
- Canal de mensageria plugável (Telegram inicial, Slack/WhatsApp/CLI futuros)
- Máquina de estados robusta para ciclo de vida de demandas
- Registry extensível de agentes por domínio
- Configuração centralizada em platform.yaml
- Testes com cobertura mínima de 80%

**Non-Goals:**
- Interface web ou dashboard gráfico
- Suporte a múltiplos usuários simultâneos na v1
- Deploy em produção com alta disponibilidade
- Treinamento ou fine-tuning de modelos
- Execução de agentes sem isolamento Docker

## Decisions

### D1: Python com módulos independentes (não microserviços)
Cada componente (barramento, orchestrator, adapters, registry) será um módulo Python dentro de um monorepo, não microserviços separados.

**Rationale:** Na fase inicial, a complexidade de comunicação inter-serviços (HTTP, gRPC, filas) é desnecessária. Módulos Python com interfaces ABC oferecem o mesmo desacoplamento com muito menos overhead. Migração para microserviços é possível no futuro pois os contratos ABC já existem.

**Alternativa descartada:** Microserviços desde o início — overhead operacional injustificado para v1.

### D2: Factory pattern para instanciação de providers
Um `PlatformFactory` lê `platform.yaml` e instancia as implementações corretas de `MessageBus` e `AIAgentAdapter`. O orquestrador recebe as interfaces injetadas via construtor.

**Rationale:** Injeção de dependência via construtor + factory centralizado garante que nenhum componente importa implementações concretas. A factory é o único ponto que conhece o mapeamento provider → implementação.

**Alternativa descartada:** Service locator — esconde dependências e dificulta testes.

### D3: Subprocess para Claude Code CLI
O `ClaudeCodeAdapter` invoca `claude --print` via `subprocess.run()` com prompt via stdin. Output é capturado e retornado como string.

**Rationale:** Aproveita a assinatura existente do usuário sem API key. É a forma suportada de integração programática com Claude Code. Limitação: não suporta interação bidirecional em tempo real, mas os pontos de decisão humana são roteados separadamente via callbacks.

**Alternativa descartada:** API direta Anthropic — exigiria API key separada e duplicaria custos.

### D4: JSON para persistência de estado
O orquestrador persiste estado de cada demanda em arquivos JSON no diretório `state/`. Cada demanda tem seu arquivo `{demand_id}.json`.

**Rationale:** Simplicidade máxima para v1. Sem necessidade de banco de dados. JSON é legível por humanos para debug. Migração para SQLite ou banco real é trivial pois o acesso é centralizado no orquestrador.

**Alternativa descartada:** SQLite — overhead desnecessário para volume esperado na v1.

### D5: Docker para isolamento de agentes
Cada agente executa dentro de um container Docker/devcontainer com acesso restrito ao filesystem e rede.

**Rationale:** Agentes de IA executando código arbitrário precisam de isolamento de segurança. Docker fornece sandboxing de filesystem, rede e processos. Devcontainers adicionam reprodutibilidade do ambiente de desenvolvimento.

**Alternativa descartada:** Execução direta no host — risco de segurança inaceitável.

### D6: AGENTS.md como fonte única de contexto com symlinks
Cada agente tem um AGENTS.md com todo seu contexto. CLAUDE.md, GEMINI.md e COPILOT.md são symlinks para AGENTS.md commitados no git.

**Rationale:** Elimina duplicação de contexto entre providers. Ao adicionar novo provider, basta criar mais um symlink. AGENTS.md é agnóstico a provider — contém apenas domínio, responsabilidades e protocolos.

## Risks / Trade-offs

**[Subprocess CLI pode ser lento]** → Aceitável para v1. Prompts grandes podem demorar. Mitigação: timeout configurável e retry com backoff exponencial.

**[JSON state pode corromper em crash]** → Mitigação: escrita atômica com write-to-temp + rename. Para v1 o risco é baixo.

**[Docker adiciona latência no startup de agentes]** → Mitigação: manter containers pré-aquecidos ou usar devcontainers com cache de layers.

**[Whisper API tem custo por chamada de voz]** → Trade-off aceitável. Volume esperado é baixo na v1. Alternativas locais (whisper.cpp) podem ser consideradas no futuro.

**[Worktrees git podem acumular e consumir disco]** → Mitigação: limpeza automática de worktrees após conclusão de demanda.

## Estrutura de Diretórios

```
ai-dev-platform/
├── platform.yaml              # Configuração centralizada
├── src/
│   ├── __init__.py
│   ├── factory.py             # PlatformFactory
│   ├── barramento/
│   │   ├── __init__.py
│   │   ├── interface.py       # ABC MessageBus
│   │   ├── telegram.py        # TelegramMessageBus
│   │   └── cli.py             # CLIMessageBus
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── engine.py          # Máquina de estados
│   │   └── state.py           # Persistência JSON
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── interface.py       # ABC AIAgentAdapter
│   │   └── claude_code.py     # ClaudeCodeAdapter
│   └── registry/
│       ├── __init__.py
│       └── registry.py        # Catálogo de agentes
├── agents/
│   ├── po/
│   │   ├── AGENTS.md
│   │   ├── CLAUDE.md -> AGENTS.md
│   │   ├── skills/
│   │   └── tools.yaml
│   ├── dev-orchestrator/
│   ├── qa/
│   └── dev-web/
├── specs/                     # Submodulos de repos
├── state/                     # Estado persistido (JSON)
├── tests/
│   ├── test_barramento.py
│   ├── test_orchestrator.py
│   ├── test_adapters.py
│   └── test_registry.py
└── registry.yaml              # Catálogo de agentes
```

## Open Questions

- Como lidar com timeout de agentes que ficam travados em execução longa?
- Qual estratégia de retry quando o CLI do Claude Code falha por erro transitório?
- Como escalar para múltiplos usuários simultâneos em versões futuras?
- Qual formato exato de contexto passar ao agente via subprocess stdin?
