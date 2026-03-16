## Context

A plataforma ai-dev-platform é uma biblioteca Python que orquestra agentes de IA (PO, Dev, QA) para executar ciclos completos de desenvolvimento. Hoje não existe entry point executável — o usuário precisa escrever código Python para instanciar factory, registrar providers e rodar o engine. As dependências (claude CLI, git, gh, Node.js) precisam estar instaladas no host, poluindo o ambiente.

O objetivo é criar um CLI chamado `ai-dev-team` que empacota tudo em Docker e permite gerenciar múltiplos "times" de desenvolvimento, cada um com seu bot Telegram, container e repo alvo.

## Goals / Non-Goals

**Goals:**
- CLI `ai-dev-team` instalável via pip com comandos intuitivos
- Cada time roda em container Docker isolado com todas as dependências
- Setup em menos de 5 minutos: `create` → preencher `.env` → `start`
- Suporte a múltiplos times rodando em paralelo
- Agentes dentro do container conseguem subir infra (banco, Redis) via docker.sock
- Daemon em loop infinito escutando Telegram

**Non-Goals:**
- Interface web ou dashboard (v1 é CLI + Telegram)
- Orquestração entre times (cada time é independente)
- Auto-scaling ou clustering de containers
- Suporte a providers além de Claude Code e Telegram na v1
- CI/CD integrado (o agente cria PR, CI existente do repo cuida do resto)

## Decisions

### 1. CLI framework: Click

**Escolha**: Click (não Typer)

**Alternativas**: Typer (wrapper de Click com type hints), argparse (stdlib)

**Razão**: Click é maduro, amplamente adotado, sem dependências extras pesadas. Typer adiciona camada desnecessária para o número de comandos que temos. argparse é verboso demais.

### 2. Estrutura de diretórios: `~/.ai-dev-team/teams/<nome>/`

**Escolha**: Diretório home do usuário com subdiretório por time

**Alternativas**: XDG dirs (`~/.config/ai-dev-team`), diretório do projeto (`.ai-dev-team/`)

**Razão**: `~/.ai-dev-team/` é simples e previsível. XDG fragmenta config e data em diretórios separados sem benefício real. Dentro do projeto poluiria o repo alvo.

### 3. Um docker-compose.yml por time

**Escolha**: Cada time tem seu próprio `docker-compose.yml` gerado no `create`

**Alternativas**: Um compose global com múltiplos services, Docker API diretamente

**Razão**: Compose por time permite `start/stop` independente, configuração isolada, e o usuário pode inspecionar/editar se necessário. Compose global acoplaria os times.

### 4. Imagem Docker única compartilhada

**Escolha**: Uma imagem base `ai-dev-team:latest` usada por todos os times

**Alternativas**: Build por time, imagem por stack (Python, Node, etc.)

**Razão**: Todos os times usam as mesmas ferramentas (claude CLI, git, gh). Build por time desperdiça espaço. A diferenciação está nos volumes e env vars, não na imagem.

### 5. Docker socket para infra do projeto

**Escolha**: Montar `/var/run/docker.sock` no container

**Alternativas**: Docker-in-Docker (privileged), não suportar infra

**Razão**: docker.sock permite que agentes executem `docker-compose up` para subir banco/Redis do projeto alvo. DinD requer `privileged: true` (pior segurança) e tem performance ruim. Não suportar infra limitaria demais os agentes.

### 6. Auth Claude via CLAUDE_CODE_OAUTH_TOKEN

**Escolha**: Token OAuth passado via variável de ambiente

**Alternativas**: Montar `~/.claude/` no container, ANTHROPIC_API_KEY

**Razão**: Variável de ambiente é o mecanismo mais limpo para Docker. Montar diretório acopla à estrutura do host. API key muda o modelo de cobrança (pay-per-use vs assinatura).

### 7. Entry point do container: daemon mode

**Escolha**: O container executa `python -m src.daemon` que roda loop infinito

**Alternativas**: Entrypoint customizado com script bash, supervisord

**Razão**: Módulo Python puro é testável e debugável. O daemon inicializa factory, registra providers, conecta ao Telegram e entra em loop `asyncio`. Graceful shutdown via SIGTERM.

## Risks / Trade-offs

**[Docker socket expõe engine do host]** → Mitigação: aceitável para uso pessoal. Documentar o risco. Em versão futura, avaliar Sysbox ou rootless Docker.

**[Token OAuth pode expirar]** → Mitigação: o daemon detecta erro 401 do claude CLI e notifica via Telegram pedindo renovação do token.

**[Imagem Docker grande (Node.js + Python + ferramentas)]** → Mitigação: usar multi-stage build. Camada base com ferramentas, camada final só com runtime. Estimativa: ~800MB.

**[Worktrees dentro de container]** → Mitigação: o volume `/workspace` é o repo. Worktrees são criados dentro de `/workspace/.worktrees/`. Git opera normalmente pois o `.git` está acessível.

**[Múltiplos times no mesmo host consomem recursos]** → Mitigação: limitar memória/CPU por container no compose. Default: 2GB RAM, 2 CPUs.

## Migration Plan

1. Criar módulo `cli/` com entry points Click
2. Criar templates de `docker-compose.yml` e `config.yaml`
3. Reescrever Dockerfile com Node.js + claude CLI + gh
4. Criar módulo `daemon.py` com loop infinito + graceful shutdown
5. Adaptar `factory.py` para ler config de env vars + config.yaml
6. Registrar entry point `ai-dev-team` no pyproject.toml
7. Testar: `pip install -e .` → `ai-dev-team create test --repo .` → `ai-dev-team start test`

**Rollback**: Nenhum dado existente é afetado. O código atual da biblioteca continua funcionando. O CLI é uma camada adicional.
