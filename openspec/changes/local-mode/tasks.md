# Tasks: local-mode

## PathResolver

- [x] Criar `src/path_resolver.py` com classe PathResolver (mode: local/docker, base_dir)
- [x] Implementar properties: workspace, agents_dir, state_dir, config_path, pipeline_dir, env_path, global_skills_dir
- [x] Testes unitários para PathResolver (modo local e docker)

## Daemon — modo local

- [x] Refatorar `daemon.py` para receber PathResolver em vez de caminhos hardcoded
- [x] Remover caminhos hardcoded `/workspace`, `/app/agents`, `/app/state`, `/app/config.yaml`
- [x] Adicionar carregamento de `.env` via python-dotenv no modo local
- [x] Validar tokens obrigatórios antes de iniciar no modo local
- [x] Manter compatibilidade com modo Docker (PathResolver mode="docker")
- [x] Testes para daemon com PathResolver local

## CLI — create local

- [x] Modificar comando `create`: sem `--repo` cria `.ai-squad/` no cwd
- [x] Criar template de config.yaml local (sem repo_path, sem docker-compose)
- [x] Copiar agents/ e pipeline/ do preset para `.ai-squad/`
- [x] Gerar `.env` com placeholders em `.ai-squad/.env`
- [x] Criar diretório `state/` em `.ai-squad/`
- [x] Erro se `.ai-squad/` já existe no cwd
- [x] Manter `create --repo` com comportamento atual (Docker)
- [x] Testes para create local e create Docker

## CLI — start com detecção automática

- [x] Implementar detecção automática: .ai-squad/ no cwd → local, senão → Docker
- [x] Adicionar flags `--local` e `--docker` (mutuamente exclusivas)
- [x] Modo local: carregar config, .env, iniciar daemon foreground
- [x] Modo Docker: manter comportamento atual (docker compose up)
- [x] Signal handling: Ctrl+C → shutdown graceful no modo local
- [x] Testes para detecção automática e flags

## CLI — stop/remove/status adaptados

- [x] `stop`: no modo local, informar que basta Ctrl+C
- [x] `remove`: suportar remoção de `.ai-squad/` local
- [x] `status`: funcionar em ambos os modos
- [x] `list`: listar times locais (.ai-squad/ no cwd) e globais (~/.ai-squad/teams/)
- [x] Testes para comandos adaptados
