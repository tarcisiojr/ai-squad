"""Resolução dinâmica de caminhos baseada no modo de execução (local vs docker)."""

from pathlib import Path


class PathResolver:
    """Resolve caminhos do sistema baseado no modo de execução.

    Modo local: caminhos relativos ao diretório do projeto (.ai-squad/)
    Modo docker: caminhos absolutos dentro do container
    """

    def __init__(self, mode: str, base_dir: Path | None = None) -> None:
        if mode not in ("local", "docker"):
            raise ValueError(f"Modo inválido: {mode}. Use 'local' ou 'docker'.")
        self.mode = mode
        self._base = Path(base_dir).resolve() if base_dir else Path.cwd()

    @property
    def workspace(self) -> Path:
        """Diretório do repositório/projeto alvo."""
        if self.mode == "docker":
            return Path("/workspace")
        return self._base

    @property
    def agents_dir(self) -> Path:
        """Diretório com AGENTS.md de cada agente."""
        if self.mode == "docker":
            return Path("/app/agents")
        return self._base / ".ai-squad" / "agents"

    @property
    def state_dir(self) -> Path:
        """Diretório de persistência de estado (JSON)."""
        if self.mode == "docker":
            return Path("/app/state")
        return self._base / ".ai-squad" / "state"

    @property
    def config_path(self) -> Path:
        """Caminho do config.yaml do time."""
        if self.mode == "docker":
            return Path("/app/config.yaml")
        return self._base / ".ai-squad" / "config.yaml"

    @property
    def pipeline_dir(self) -> Path:
        """Diretório do pipeline (pipeline.yaml + steps/)."""
        if self.mode == "docker":
            return Path("/app/pipeline")
        return self._base / ".ai-squad" / "pipeline"

    @property
    def env_path(self) -> Path:
        """Caminho do arquivo .env com tokens."""
        if self.mode == "docker":
            return Path("/app/.env")
        return self._base / ".ai-squad" / ".env"

    @property
    def global_skills_dir(self) -> Path:
        """Diretório de skills globais compartilhadas entre times."""
        if self.mode == "docker":
            return Path("/app/global-skills")
        return Path.home() / ".ai-squad" / "skills"
