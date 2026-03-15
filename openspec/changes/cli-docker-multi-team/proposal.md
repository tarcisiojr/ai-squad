## Why

A plataforma hoje exige que o usuário escreva código Python para instanciar factory, registrar providers e rodar o engine. Não existe ponto de entrada executável, nem empacotamento de dependências. Para viabilizar uso próprio e futura distribuição, precisamos de um CLI (`ai-dev-team`) que abstraia toda a complexidade e rode em Docker para preservar o ambiente do host.

## What Changes

- **Novo CLI `ai-dev-team`** com comandos: `create`, `start`, `stop`, `list`, `logs`, `status`
- **Modelo multi-time**: cada time é uma instância independente com bot Telegram próprio, container Docker próprio e repo alvo via volume mount
- **Estrutura `~/.ai-dev-team/teams/<nome>/`** com config, .env, docker-compose e estado por time
- **Dockerfile otimizado** com Python 3.11 + Node.js + claude CLI + git + gh CLI
- **docker-compose por time** com docker.sock montado (agentes podem subir infra do projeto)
- **Auth via `CLAUDE_CODE_OAUTH_TOKEN`** para Claude CLI dentro do container
- **Loop infinito** no container: daemon escuta Telegram e processa demandas autonomamente
- **BREAKING**: `platform.yaml` e `registry.yaml` migram para dentro da estrutura do time

## Capabilities

### New Capabilities
- `cli-entrypoint`: CLI principal `ai-dev-team` com comandos de gerenciamento de times (create, start, stop, list, logs, status)
- `team-management`: Estrutura multi-time em `~/.ai-dev-team/teams/<nome>/` com config, .env template, docker-compose e state isolados por time
- `docker-packaging`: Dockerfile com todas as dependências (Python, Node.js, claude CLI, git, gh) e docker-compose com docker.sock para agentes subirem infra
- `daemon-loop`: Processo daemon que roda em loop infinito dentro do container, escutando Telegram e despachando demandas pelo engine de orquestração

### Modified Capabilities
- `platform-config`: **BREAKING** — configuração migra de `platform.yaml` na raiz para `~/.ai-dev-team/teams/<nome>/config.yaml`, com adição de campos para repo path e credenciais via .env
- `messaging-bus`: Telegram passa a ser o provider padrão (não mais CLI), com bot token por time e CHAT_ID configurável

## Impact

- **Código novo**: módulo `cli/` com entry point, gerenciador de times, templates
- **Dockerfile**: reescrita completa (adicionar Node.js, claude CLI, gh CLI)
- **docker-compose**: novo arquivo template por time
- **factory.py**: precisa suportar inicialização via variáveis de ambiente (.env)
- **engine.py**: precisa de modo daemon (loop infinito + graceful shutdown)
- **pyproject.toml**: adicionar entry point `ai-dev-team` e dependência `click` (ou `typer`) para CLI
- **Dependências novas**: click/typer, python-dotenv
