"""Gerenciador de times ai-squad."""

import re
import shutil
from pathlib import Path

import click
import yaml

from ai_squad.cli.templates.config import (
    DOCKER_COMPOSE_TEMPLATE,
    PLACEHOLDER_PREFIX,
    get_env_template,
)

# Padrão seguro para nomes de time: alfanumérico, _ e -, máx 64 caracteres
_SAFE_TEAM_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")


def validate_team_name(name: str) -> None:
    """Valida nome do time para prevenir path traversal e injection."""
    if not _SAFE_TEAM_NAME.match(name):
        raise click.BadParameter(
            f"Nome inválido: '{name}'. Use apenas letras, números, _ e - "
            f"(máx 64 caracteres, começando com alfanumérico)."
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

    Cada time é armazenado em ~/.ai-squad/teams/<nome>/ com:
    - config.yaml
    - .env
    - docker-compose.yml
    - state/
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = Path.home() / ".ai-squad"
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

    def _build_config_from_preset(
        self, preset: str, repo_path: str = "", messaging_provider: str = "telegram"
    ) -> str:
        """Gera config.yaml dinamicamente a partir dos agentes do preset."""
        agents_dir = self._find_preset_dir(preset, "agents")

        config: dict = {
            "ai_provider": "claude-agent-sdk",
            "messaging_provider": messaging_provider,
            "ai_model": "claude-sonnet-4-20250514",
            "agent_timeout": 300,
            "squad_lead": {"name": "Squad Lead", "avatar": "👨‍💼"},
            "agents": {},
        }

        if repo_path:
            config["repo_path"] = repo_path
            config["state_dir"] = "state/"

        # Helpdesk preset: habilita knowledge base
        if preset == "helpdesk":
            config["knowledge"] = {
                "enabled": True,
                "use_qmd": False,
                "knowledge_dir": "knowledge/",
            }

        if agents_dir:
            for agent_dir in sorted(agents_dir.iterdir()):
                if not agent_dir.is_dir() or agent_dir.name == "squad-lead":
                    continue
                name = agent_dir.name.replace("-", " ").title()
                config["agents"][agent_dir.name] = {
                    "name": name,
                    "avatar": "🤖",
                    "command": f"/{agent_dir.name}",
                }

        return yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _find_preset_dir(self, preset: str, subdir: str) -> Path | None:
        """Localiza diretório de um preset (agents/ ou pipeline/)."""
        sources = [
            Path(__file__).resolve().parent.parent / "presets" / preset / subdir,
            Path.cwd() / "src" / "presets" / preset / subdir,
        ]
        for source in sources:
            if source.exists() and source.is_dir():
                return source
        return None

    def create_local(
        self,
        team_name: str,
        project_dir: Path | None = None,
        preset: str = "dev-openspec",
        messaging_provider: str = "telegram",
    ) -> Path:
        """Cria estrutura .ai-squad/ no diretório do projeto (modo local)."""
        project = (project_dir or Path.cwd()).resolve()
        squad_dir = project / ".ai-squad"

        if squad_dir.exists():
            raise TeamExistsError("Já existe uma squad neste diretório (.ai-squad/).")

        squad_dir.mkdir(parents=True)

        # Cria diretório de estado
        (squad_dir / "state").mkdir()

        # Gera config.yaml a partir dos agentes do preset
        config_content = self._build_config_from_preset(
            preset, messaging_provider=messaging_provider
        )
        (squad_dir / "config.yaml").write_text(config_content, encoding="utf-8")

        # Gera .env com placeholders (dinâmico por provider)
        env_content = get_env_template(messaging_provider)
        (squad_dir / ".env").write_text(env_content, encoding="utf-8")

        # Copia agents/ e pipeline/ do preset
        self._copy_default_agents(squad_dir, preset=preset)
        self._copy_default_pipeline(squad_dir, preset=preset)

        # Copia knowledge/ do preset (helpdesk)
        self._copy_preset_subdir(squad_dir, preset, "knowledge")

        return squad_dir

    def create(
        self,
        team_name: str,
        repo_path: str,
        preset: str = "dev-openspec",
        messaging_provider: str = "telegram",
    ) -> Path:
        """Cria estrutura completa para um novo time."""
        repo = Path(repo_path).resolve()
        if not repo.exists():
            raise FileNotFoundError(f"Diretório do repositório não encontrado: {repo}")

        if self.exists(team_name):
            raise TeamExistsError(f"Time '{team_name}' já existe. Use outro nome.")

        team_dir = self.get_path(team_name)
        team_dir.mkdir(parents=True, exist_ok=True)

        # Cria diretório de estado
        (team_dir / "state").mkdir(exist_ok=True)

        # Gera config.yaml a partir dos agentes do preset
        config_content = self._build_config_from_preset(
            preset, repo_path=str(repo), messaging_provider=messaging_provider
        )
        (team_dir / "config.yaml").write_text(config_content, encoding="utf-8")

        # Gera .env com placeholders (dinâmico por provider)
        env_content = get_env_template(messaging_provider)
        (team_dir / ".env").write_text(env_content, encoding="utf-8")

        # Copia Whisper service para o time
        self._copy_whisper_service(team_dir)
        whisper_context = "./whisper"

        # Gera docker-compose.yml
        compose_content = DOCKER_COMPOSE_TEMPLATE.format(
            team_name=team_name,
            repo_path=str(repo),
            whisper_context=whisper_context,
        )
        (team_dir / "docker-compose.yml").write_text(compose_content, encoding="utf-8")

        # Copia pasta agents/ para customização pelo usuário
        self._copy_default_agents(team_dir, preset=preset)

        # Copia pipeline/ do preset para o time
        self._copy_default_pipeline(team_dir, preset=preset)

        # Copia knowledge/ do preset (helpdesk)
        self._copy_preset_subdir(team_dir, preset, "knowledge")

        return team_dir

    def _copy_whisper_service(self, team_dir: Path) -> None:
        """Copia Whisper service para o diretório do time."""
        sources = [
            Path(__file__).resolve().parent.parent / "whisper",
            Path.cwd() / "src" / "whisper",
        ]

        for source in sources:
            if source.exists() and source.is_dir():
                dest = team_dir / "whisper"
                shutil.copytree(source, dest, dirs_exist_ok=True)
                return

    def _copy_default_pipeline(self, team_dir: Path, preset: str = "dev-openspec") -> None:
        """Copia pipeline/ do preset para o diretório do time."""
        sources = [
            Path(__file__).resolve().parent.parent / "presets" / preset / "pipeline",
            Path.cwd() / "src" / "presets" / preset / "pipeline",
        ]

        for source in sources:
            if source.exists() and source.is_dir():
                dest = team_dir / "pipeline"
                shutil.copytree(source, dest, dirs_exist_ok=True)
                return

    def _copy_preset_subdir(self, team_dir: Path, preset: str, subdir: str) -> None:
        """Copia subdiretório genérico do preset (ex: knowledge/) se existir."""
        source = self._find_preset_dir(preset, subdir)
        if source:
            dest = team_dir / subdir
            shutil.copytree(source, dest, dirs_exist_ok=True)

    def _copy_default_agents(self, team_dir: Path, preset: str = "dev-openspec") -> None:
        """Copia agents/ do preset para o diretório do time."""
        sources = [
            Path(__file__).resolve().parent.parent / "presets" / preset / "agents",
            Path.cwd() / "src" / "presets" / preset / "agents",
        ]

        for source in sources:
            if source.exists() and source.is_dir():
                dest = team_dir / "agents"
                shutil.copytree(source, dest, dirs_exist_ok=True)
                return

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

            teams.append(
                {
                    "name": team_dir.name,
                    "repo_path": repo_path,
                    "team_dir": str(team_dir),
                }
            )

        return teams

    def validate_env(self, team_name: str) -> list[str]:
        """Valida se .env tem todas as variáveis obrigatórias preenchidas.

        Verifica tokens comuns + tokens específicos do provider de mensageria.
        Retorna lista de variáveis que ainda contêm placeholders.
        """
        if not self.exists(team_name):
            raise TeamNotFoundError(f"Time '{team_name}' não encontrado.")

        env_path = self.get_path(team_name) / ".env"
        if not env_path.exists():
            return ["CLAUDE_CODE_OAUTH_TOKEN"]

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

        # Descobre providers do config.yaml para montar lista de tokens
        required_vars: list[str] = []
        config_path = self.get_path(team_name) / "config.yaml"
        if config_path.exists():
            import yaml

            from ai_squad.factory import _PROVIDER_AI_TOKENS

            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            # Token obrigatório do provider de IA
            ai_provider = data.get("ai_provider", "claude-agent-sdk")
            ai_token = _PROVIDER_AI_TOKENS.get(ai_provider, "CLAUDE_CODE_OAUTH_TOKEN")
            if ai_token:
                required_vars.append(ai_token)

            # Tokens do provider de mensageria
            provider_name = data.get("messaging_provider", "telegram")
            try:
                from ai_squad.messaging.registry import get as get_provider
                from ai_squad.messaging.registry import load_builtin_providers

                load_builtin_providers()
                provider_cls = get_provider(provider_name)
                required_vars.extend(provider_cls.required_env_vars())
            except (ValueError, ImportError):
                pass

        # Verifica quais obrigatórias estão faltando ou com placeholder
        missing = []
        for var in required_vars:
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
