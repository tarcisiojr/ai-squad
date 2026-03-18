## Context

O ai-squad roda exclusivamente dentro de containers Docker. O daemon assume caminhos fixos (`/workspace`, `/app/agents`, `/app/state`), o CLI gerencia lifecycle via `docker compose`, e o `create` sempre gera `docker-compose.yml`. Isso significa que mesmo para um teste rápido o usuário precisa de Docker Desktop rodando, build de imagem (~5min na primeira vez) e gerenciamento de containers.

O engine, adapters e orchestrator já são agnósticos a caminhos — recebem `workspace`, `agents_dir` etc. como parâmetros. O acoplamento está concentrado em dois pontos: `daemon.py` (caminhos hardcoded) e `cli/main.py` (lifecycle Docker).

## Goals / Non-Goals

**Goals:**
- Rodar o daemon como processo Python local sem Docker
- `ai-squad create` sem `--repo` cria estrutura local no diretório corrente
- `ai-squad start` detecta automaticamente modo local vs Docker
- Manter modo Docker funcional como opt-in
- `.env` carregado automaticamente do `.ai-squad/.env`

**Non-Goals:**
- Whisper (transcrição de áudio) no modo local
- Daemon como serviço background do OS (systemd, launchd)
- Migração automática de times Docker → local
- Mudar comportamento do modo Docker existente

## Decisions

### 1. PathResolver centraliza resolução de caminhos

**Decisão:** Criar classe `PathResolver` que resolve caminhos baseado no modo de execução.

**Alternativas consideradas:**
- (A) Cada módulo resolve seus caminhos → espalhado, inconsistente
- (B) Variáveis de ambiente para cada caminho → verboso, error-prone
- (C) Classe centralizada com dois perfis (local/docker) → escolhida

```python
class PathResolver:
    def __init__(self, mode: str, base_dir: Path):
        self.mode = mode  # "local" ou "docker"
        self._base = base_dir

    @property
    def workspace(self) -> Path:
        if self.mode == "docker":
            return Path("/workspace")
        return self._base  # cwd ou pai do .ai-squad/

    @property
    def agents_dir(self) -> Path:
        if self.mode == "docker":
            return Path("/app/agents")
        return self._base / ".ai-squad" / "agents"

    @property
    def state_dir(self) -> Path:
        if self.mode == "docker":
            return Path("/app/state")
        return self._base / ".ai-squad" / "state"

    @property
    def config_path(self) -> Path:
        if self.mode == "docker":
            return Path("/app/config.yaml")
        return self._base / ".ai-squad" / "config.yaml"

    @property
    def pipeline_dir(self) -> Path:
        if self.mode == "docker":
            return Path("/app/pipeline")
        return self._base / ".ai-squad" / "pipeline"

    @property
    def env_path(self) -> Path:
        if self.mode == "docker":
            return Path("/app/.env")
        return self._base / ".ai-squad" / ".env"

    @property
    def global_skills_dir(self) -> Path:
        if self.mode == "docker":
            return Path("/app/global-skills")
        return Path.home() / ".ai-squad" / "skills"
```

**Justificativa:** Um único ponto de verdade para todos os caminhos. Daemon e CLI consultam o PathResolver em vez de ter caminhos hardcoded.

### 2. Detecção automática de modo no `start`

**Decisão:** `ai-squad start <nome>` detecta o modo pela presença de `.ai-squad/` no cwd.

```
Prioridade:
1. Flag explícita (--local, --docker) → usa o que o usuário pediu
2. ./.ai-squad/ existe → modo local
3. ~/.ai-squad/teams/<nome>/ existe → modo Docker
4. Nenhum → erro
```

**Justificativa:** Zero-config para o caso comum. Se o usuário está dentro do projeto e tem `.ai-squad/`, ele quer rodar local. Se não, cai no modo Docker global.

### 3. `create` sem `--repo` cria estrutura local

**Decisão:** O `--repo` diferencia os dois modos de criação.

| Comando | Onde cria | O que gera |
|---------|-----------|------------|
| `ai-squad create X` | `./.ai-squad/` | config, agents, pipeline, .env, state |
| `ai-squad create X --repo ~/app` | `~/.ai-squad/teams/X/` | + docker-compose.yml, whisper/ |

**Justificativa:** `--repo` indica que o workspace está em outro lugar (precisa de volume Docker). Sem `--repo`, o workspace é o cwd (modo local).

### 4. Template local sem `repo_path`

**Decisão:** O config.yaml local não tem `repo_path` — o workspace é sempre o diretório pai do `.ai-squad/`.

**Justificativa:** Redundante no modo local. Simplifica template e evita inconsistência (ex: mover o projeto e esquecer de atualizar o path).

### 5. `.env` carregado via python-dotenv

**Decisão:** No modo local, o daemon carrega `.ai-squad/.env` via `python-dotenv` antes de iniciar.

**Justificativa:** O python-dotenv já é dependência do projeto. No modo Docker, o `env_file` do docker-compose faz isso. No modo local, precisamos do equivalente.

### 6. Modo local roda foreground com signal handling

**Decisão:** `ai-squad start X` (local) roda o daemon no processo atual. Ctrl+C (SIGINT) para gracefully.

**Justificativa:** Simplicidade. O usuário vê logs em tempo real, pode cancelar facilmente. Sem complexidade de gerenciamento de processos background.

## Risks / Trade-offs

- **[Risco] Usuário roda local sem tokens configurados** → Mitigação: validar `.env` antes de iniciar (já existe `validate_env`)
- **[Risco] Agentes modificam repo sem isolamento** → Mitigação: é o comportamento desejado no modo local; documentar que Docker é recomendado para produção
- **[Risco] Dois modos de execução aumentam superfície de teste** → Mitigação: PathResolver testável unitariamente; daemon recebe paths via parâmetro
- **[Trade-off] Sem Whisper no modo local** → Aceito por simplicidade; pode ser adicionado depois como processo Python opcional
