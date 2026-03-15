"""Gerenciador de times ai-dev-team."""

from pathlib import Path

from src.cli.templates.config import (
    CONFIG_YAML_TEMPLATE,
    DOCKER_COMPOSE_TEMPLATE,
    ENV_TEMPLATE,
    PLACEHOLDER_PREFIX,
    REQUIRED_ENV_VARS,
)


class TeamExistsError(Exception):
    """Erro quando time já existe."""

    pass


class TeamNotFoundError(Exception):
    """Erro quando time não encontrado."""

    pass


class InvalidEnvError(Exception):
    """Erro quando .env contém placeholders não preenchidos."""

    pass


class TeamManager:
    """Gerencia estrutura de diretórios e configuração de times.

    Cada time é armazenado em ~/.ai-dev-team/teams/<nome>/ com:
    - config.yaml
    - .env
    - docker-compose.yml
    - state/
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = Path.home() / ".ai-dev-team"
        self._base_dir = base_dir
        self._teams_dir = base_dir / "teams"

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    @property
    def teams_dir(self) -> Path:
        return self._teams_dir

    def exists(self, team_name: str) -> bool:
        """Verifica se um time existe."""
        return self.get_path(team_name).exists()

    def get_path(self, team_name: str) -> Path:
        """Retorna caminho do diretório de um time."""
        return self._teams_dir / team_name

    def create(self, team_name: str, repo_path: str) -> Path:
        """Cria estrutura completa para um novo time."""
        repo = Path(repo_path).resolve()
        if not repo.exists():
            raise FileNotFoundError(
                f"Diretório do repositório não encontrado: {repo}"
            )

        if self.exists(team_name):
            raise TeamExistsError(
                f"Time '{team_name}' já existe. Use outro nome."
            )

        team_dir = self.get_path(team_name)
        team_dir.mkdir(parents=True, exist_ok=True)

        # Cria diretório de estado
        (team_dir / "state").mkdir(exist_ok=True)

        # Gera config.yaml
        config_content = CONFIG_YAML_TEMPLATE.format(repo_path=str(repo))
        (team_dir / "config.yaml").write_text(config_content, encoding="utf-8")

        # Gera .env com placeholders
        (team_dir / ".env").write_text(ENV_TEMPLATE, encoding="utf-8")

        # Gera docker-compose.yml
        compose_content = DOCKER_COMPOSE_TEMPLATE.format(
            team_name=team_name,
            repo_path=str(repo),
        )
        (team_dir / "docker-compose.yml").write_text(
            compose_content, encoding="utf-8"
        )

        return team_dir

    def list_teams(self) -> list[dict[str, str]]:
        """Lista todos os times com nome e repo path."""
        teams = []
        if not self._teams_dir.exists():
            return teams

        for team_dir in sorted(self._teams_dir.iterdir()):
            if not team_dir.is_dir():
                continue

            config_path = team_dir / "config.yaml"
            repo_path = ""
            if config_path.exists():
                import yaml

                with open(config_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                repo_path = data.get("repo_path", "")

            teams.append({
                "name": team_dir.name,
                "repo_path": repo_path,
                "team_dir": str(team_dir),
            })

        return teams

    def validate_env(self, team_name: str) -> list[str]:
        """Valida se .env tem todas as variáveis obrigatórias preenchidas.

        Retorna lista de variáveis que ainda contêm placeholders.
        """
        if not self.exists(team_name):
            raise TeamNotFoundError(f"Time '{team_name}' não encontrado.")

        env_path = self.get_path(team_name) / ".env"
        if not env_path.exists():
            return list(REQUIRED_ENV_VARS)

        env_content = env_path.read_text(encoding="utf-8")

        # Extrai variáveis do .env
        env_vars: dict[str, str] = {}
        for line in env_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

        # Verifica quais obrigatórias estão faltando ou com placeholder
        missing = []
        for var in REQUIRED_ENV_VARS:
            value = env_vars.get(var, "")
            if not value or value.startswith(PLACEHOLDER_PREFIX):
                missing.append(var)

        return missing

    def remove(self, team_name: str) -> None:
        """Remove um time e seus arquivos."""
        if not self.exists(team_name):
            raise TeamNotFoundError(f"Time '{team_name}' não encontrado.")

        import shutil

        shutil.rmtree(self.get_path(team_name))
