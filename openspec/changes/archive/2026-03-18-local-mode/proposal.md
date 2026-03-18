# Proposal: Modo Local (sem Docker)

## Why

Hoje o ai-squad **depende de Docker** para funcionar. O daemon roda dentro de um container, os caminhos são hardcoded (`/workspace`, `/app/agents`), e o CLI só sabe fazer `docker compose up/down`. Isso cria fricção desnecessária para desenvolvimento e testes — o usuário precisa construir imagem, gerenciar containers e volumes, mesmo para um teste rápido.

O Docker deve ser uma **feature opcional** para quem quer isolamento em produção, não um pré-requisito.

## What Changes

### Modo local como default

- `ai-squad create MeuTime` (sem `--repo`) → cria `.ai-squad/` no diretório corrente
- `ai-squad start MeuTime` → detecta modo automaticamente e roda foreground no terminal
- Workspace = diretório corrente (pai do `.ai-squad/`)
- Ctrl+C para parar

### Modo Docker como opt-in

- `ai-squad create MeuTime --repo ~/app` → cria em `~/.ai-squad/teams/` (como hoje)
- `ai-squad start MeuTime --docker` → sobe container (como hoje)
- Docker permanece funcional para quem precisa de isolamento

### Detecção automática no `start`

```
./.ai-squad/ existe?
  SIM → modo local (foreground)
  NÃO → procura ~/.ai-squad/teams/<nome>/
    SIM → modo Docker (background)
    NÃO → erro
```

Flags `--local` e `--docker` forçam o modo desejado.

## Capabilities

### local-execution
Daemon roda como processo Python direto no terminal do usuário, sem Docker.

### path-resolver
Resolução dinâmica de caminhos: Docker usa `/workspace`, `/app/*`; local usa cwd e `.ai-squad/`.

### local-create
`ai-squad create` sem `--repo` cria estrutura `.ai-squad/` no diretório corrente, sem docker-compose.yml nem whisper.

### auto-detect-mode
`ai-squad start` detecta automaticamente se é local ou Docker baseado na presença de `.ai-squad/` no cwd.

## Impact

### Arquivos modificados
- `src/daemon.py` — resolução dinâmica de caminhos, carregamento de `.env`
- `src/cli/main.py` — novos modos no `create` e `start`, detecção automática
- `src/cli/team_manager.py` — suporte a criação local (`.ai-squad/`)
- `src/cli/templates/config.py` — template local (sem repo_path, sem Docker)
- `src/factory.py` — PlatformConfig sem dependência de caminhos Docker

### Arquivos novos
- `src/path_resolver.py` — resolve caminhos baseado no modo (local vs Docker)

### Sem impacto
- Engine, adapters, orchestrator — já são agnósticos a caminhos (recebem via parâmetro)
- Presets, agents, pipeline — sem mudança
- Modo Docker existente — permanece funcional

## Non-Goals

- Whisper no modo local (pode ser adicionado depois)
- Daemon como serviço background do OS (fica foreground no terminal)
- Migração automática de times Docker para local
