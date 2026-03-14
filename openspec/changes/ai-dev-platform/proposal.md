## Why

Equipes de desenvolvimento precisam de automação inteligente que vá além de assistentes de código pontuais. Hoje, a IA ajuda a escrever trechos de código, mas não orquestra o ciclo completo de entrega — da demanda à produção. Esta plataforma cria um time de agentes especializados (PO, Dev, QA) que trabalham de forma autônoma, interagindo com o usuário apenas em pontos de decisão humana, via barramento de mensagens (Telegram inicialmente). A arquitetura é agnóstica a provider de IA e canal de mensageria, permitindo evolução sem lock-in.

## What Changes

- Criação de barramento de mensageria com interface ABC e implementação Telegram (voz + texto via Whisper)
- Criação de orquestrador de estado que controla o ciclo de vida de demandas (idle → done) sem conhecer providers concretos
- Criação de AIAgentAdapter com interface ABC e implementação Claude Code (subprocess CLI)
- Criação de Agent Registry com catálogo YAML de agentes por domínio, AGENTS.md como fonte única de contexto, e symlinks para providers
- Criação de estrutura de specs com submodulos git e contratos (OpenAPI, AsyncAPI, schemas de eventos)
- Configuração centralizada via platform.yaml para troca de providers sem alteração de código
- Isolamento de agentes via Docker/devcontainer

## Capabilities

### New Capabilities
- `messaging-bus`: Interface ABC de barramento com métodos send_message, send_approval_request, receive_message, receive_voice, notify. Implementação Telegram com identidade por persona (PO, Dev, QA)
- `orchestrator`: Máquina de estados para ciclo de vida de demandas. Persistência em JSON, despacho de agentes via adapter, roteamento de pedidos humanos ao barramento, gerenciamento de worktrees git
- `ai-agent-adapter`: Interface ABC para execução de agentes IA com métodos run, ask, status, on_human_needed. Implementação Claude Code via subprocess CLI com --print
- `agent-registry`: Catálogo YAML de agentes com domínio, protocolo, ferramentas, versão e adapter preferido. Matching entre contrato de feature e domínio declarado. Personas base: po, dev-orchestrator, qa. Subagentes por domínio
- `platform-config`: Configuração centralizada em platform.yaml para seleção de providers (IA e mensageria) e parâmetros globais
- `contract-specs`: Estrutura de contratos firmados antes do desenvolvimento (OpenAPI, AsyncAPI, schemas). CI valida que PRs não quebram contratos

### Modified Capabilities

## Impact

- **Código**: Criação de projeto Python 3.11+ greenfield com módulos independentes: barramento/, orchestrator/, adapters/, registry/, specs/
- **APIs**: Interfaces ABC definem contratos internos entre componentes. Contratos externos via OpenAPI/AsyncAPI nos specs
- **Dependências**: python-telegram-bot, openai (Whisper), pyyaml, pytest, docker SDK
- **Sistemas**: Requer Docker para isolamento de agentes. Integração com git (worktrees, submodules). Integração com Claude Code CLI
