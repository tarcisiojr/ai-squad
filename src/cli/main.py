"""CLI principal do ai-squad."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import click

from src.cli.team_manager import (
    TeamExistsError,
    TeamManager,
)


def _get_manager() -> TeamManager:
    """Retorna instância do TeamManager."""
    return TeamManager()


def _docker_compose_cmd(team_dir: Path, *args: str) -> list[str]:
    """Monta comando docker compose para um time."""
    return [
        "docker",
        "compose",
        "-f",
        str(team_dir / "docker-compose.yml"),
        *args,
    ]


def _image_exists() -> bool:
    """Verifica se a imagem ai-squad:latest existe."""
    resultado = subprocess.run(
        ["docker", "image", "inspect", "ai-squad:latest"],
        capture_output=True,
        text=True,
    )
    return resultado.returncode == 0


def _build_image() -> None:
    """Constrói a imagem Docker ai-squad:latest.

    Monta um contexto de build temporário com:
    1. Dockerfile embutido no pacote (src/docker/Dockerfile)
    2. .whl gerado via 'uv build' ou 'python -m build'
    """
    from src.docker import get_docker_dir

    dockerfile = get_docker_dir() / "Dockerfile"
    if not dockerfile.exists():
        click.echo("Erro: Dockerfile não encontrado no pacote.", err=True)
        sys.exit(1)

    source_dir = _find_source_dir()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Copia Dockerfile para o contexto temporário
        shutil.copy2(dockerfile, tmp_path / "Dockerfile")

        # Gera o .whl do pacote
        click.echo("Gerando pacote .whl...")
        if not _generate_wheel(source_dir, tmp_path):
            sys.exit(1)

        click.echo("Construindo imagem ai-squad:latest...")
        resultado = subprocess.run(
            ["docker", "build", "-t", "ai-squad:latest", str(tmp_path)],
            capture_output=False,
        )

        if resultado.returncode != 0:
            click.echo("Erro ao construir imagem Docker.", err=True)
            sys.exit(1)

    click.echo("Imagem construída com sucesso.")


def _generate_wheel(source_dir: Path, output_dir: Path) -> bool:
    """Gera .whl do pacote. Tenta uv, depois python -m build, depois pip."""
    build_commands = [
        (["uv", "build", "--wheel", "--out-dir", str(output_dir), str(source_dir)], "uv"),
        (
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(output_dir),
                str(source_dir),
            ],
            "python -m build",
        ),
        (
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "-w",
                str(output_dir),
                str(source_dir),
            ],
            "pip wheel",
        ),
    ]

    for cmd, name in build_commands:
        resultado = subprocess.run(cmd, capture_output=True, text=True)
        if resultado.returncode == 0:
            whl_files = list(output_dir.glob("*.whl"))
            if whl_files:
                click.echo(f"  .whl gerado via {name}: {whl_files[0].name}")
                return True

    click.echo(
        "Erro: não foi possível gerar o .whl.\nInstale 'uv' ou 'build': pip install build",
        err=True,
    )
    return False


def _find_source_dir() -> Path:
    """Localiza diretório com código-fonte do ai-squad (com pyproject.toml)."""
    source_ref = Path.home() / ".ai-squad" / "source_path"

    # Tenta diretório atual
    if (Path.cwd() / "pyproject.toml").exists():
        _save_source_ref(source_ref, Path.cwd())
        return Path.cwd()

    # Tenta a partir do pacote instalado (funciona em pip install -e .)
    pkg_root = Path(__file__).resolve().parent.parent.parent
    if (pkg_root / "pyproject.toml").exists():
        _save_source_ref(source_ref, pkg_root)
        return pkg_root

    # Tenta referência salva de execução anterior
    if source_ref.exists():
        saved = Path(source_ref.read_text(encoding="utf-8").strip())
        if (saved / "pyproject.toml").exists():
            return saved

    click.echo(
        "Erro: código-fonte do ai-squad não encontrado.\n"
        "Execute 'ai-squad build' uma vez de dentro do diretório do projeto,\n"
        "ou crie o arquivo ~/.ai-squad/source_path com o caminho do projeto.",
        err=True,
    )
    sys.exit(1)


def _save_source_ref(ref_path: Path, source_dir: Path) -> None:
    """Salva referência ao diretório fonte para uso futuro."""
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    ref_path.write_text(str(source_dir.resolve()), encoding="utf-8")


def _get_container_status(team_name: str) -> str:
    """Verifica status do container de um time."""
    resultado = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}}", f"adt-{team_name}"],
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        return "stopped"
    return resultado.stdout.strip()


@click.group()
@click.version_option(version="0.2.4", prog_name="ai-squad")
def cli() -> None:
    """ai-squad — Time completo de desenvolvimento autônomo por IA."""
    pass


@cli.command()
@click.argument("name")
@click.option("--repo", default=None, help="Caminho do repositório alvo (modo Docker).")
@click.option(
    "--preset",
    default="dev-openspec",
    help="Preset de pipeline/agentes (dev-openspec, infra-monitor, investment-analysis).",
)
@click.option(
    "--messaging",
    default="telegram",
    help="Provider de mensageria (telegram, cli, discord, slack, gchat).",
)
def create(name: str, repo: str | None, preset: str, messaging: str) -> None:
    """Cria um novo time. Sem --repo cria local, com --repo cria para Docker."""
    manager = _get_manager()
    try:
        if repo:
            # Modo Docker: cria em ~/.ai-squad/teams/<nome>/
            team_dir = manager.create(name, repo, preset=preset, messaging_provider=messaging)
            click.echo(
                f"Time '{name}' criado em {team_dir} (Docker, preset: {preset}, messaging: {messaging})"
            )
            click.echo("")
            click.echo("Próximos passos:")
            click.echo(f"  1. Edite o .env: {team_dir / '.env'}")
            click.echo(f"  2. Inicie o time: ai-squad start {name}")
        else:
            # Modo local: cria .ai-squad/ no diretório corrente
            squad_dir = manager.create_local(name, preset=preset, messaging_provider=messaging)
            click.echo(
                f"Squad '{name}' criada em {squad_dir} (local, preset: {preset}, messaging: {messaging})"
            )
            click.echo("")
            click.echo("Próximos passos:")
            click.echo(f"  1. Edite o .env: {squad_dir / '.env'}")
            click.echo(f"  2. Inicie: ai-squad start {name}")
    except FileNotFoundError as e:
        click.echo(f"Erro: {e}", err=True)
        sys.exit(1)
    except TeamExistsError as e:
        click.echo(f"Erro: {e}", err=True)
        sys.exit(1)


def _detect_mode(name: str) -> str:
    """Detecta modo de execução: local (.ai-squad/ no cwd) ou docker (~/.ai-squad/teams/)."""
    local_dir = Path.cwd() / ".ai-squad"
    if local_dir.exists():
        return "local"

    global_dir = Path.home() / ".ai-squad" / "teams" / name
    if global_dir.exists():
        return "docker"

    click.echo(
        f"Erro: Time '{name}' não encontrado.\n"
        f"  Local: .ai-squad/ não existe no diretório corrente\n"
        f"  Docker: ~/.ai-squad/teams/{name}/ não existe\n\n"
        f"Crie com: ai-squad create {name}",
        err=True,
    )
    sys.exit(1)


def _start_local(name: str, *, use_tui: bool = False) -> None:
    """Inicia time em modo local (foreground)."""
    import asyncio
    import logging as _logging

    from dotenv import load_dotenv

    from src.path_resolver import PathResolver

    paths = PathResolver("local", Path.cwd())

    # TUI: redireciona logging para arquivo ANTES de importar o daemon
    if use_tui:
        import os

        log_path = paths.state_dir / "tui.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        os.environ["NO_COLOR"] = "1"
        os.environ["MESSAGING_PROVIDER"] = "tui"

        # Configura logging para arquivo ANTES do daemon importar
        _logging.basicConfig(
            level=_logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            filename=str(log_path),
            filemode="w",
            force=True,
        )

    from src.daemon import Daemon

    # Carrega .env
    if paths.env_path.exists():
        load_dotenv(paths.env_path)
    else:
        click.echo(f"Erro: .env não encontrado em {paths.env_path}", err=True)
        sys.exit(1)

    # Valida tokens (comuns + provider)
    import os

    from src.cli.templates.config import PLACEHOLDER_PREFIX

    required_vars = []
    # Lê config para determinar providers
    try:
        import yaml as _yaml

        config_path = paths.config_path
        if config_path.exists():
            with open(config_path, encoding="utf-8") as _f:
                _cfg = _yaml.safe_load(_f) or {}

            # Tokens do provider de IA (usa mapeamento centralizado)
            from src.factory import _PROVIDER_AI_TOKENS

            ai_provider = _cfg.get("ai_provider", "claude-agent-sdk")
            ai_token = _PROVIDER_AI_TOKENS.get(ai_provider, "CLAUDE_CODE_OAUTH_TOKEN")
            if ai_token:
                required_vars.append(ai_token)

            # Tokens do provider de mensageria
            provider_name = _cfg.get("messaging_provider", "telegram")
            from src.messaging.registry import get as _get_provider
            from src.messaging.registry import load_builtin_providers

            load_builtin_providers()
            provider_cls = _get_provider(provider_name)
            required_vars.extend(provider_cls.required_env_vars())
    except (ValueError, ImportError):
        required_vars.append("CLAUDE_CODE_OAUTH_TOKEN")

    missing = [
        v
        for v in required_vars
        if not os.environ.get(v) or os.environ.get(v, "").startswith(PLACEHOLDER_PREFIX)
    ]
    if missing:
        click.echo("Erro: Variáveis não preenchidas no .env:")
        for var in missing:
            click.echo(f"  - {var}")
        click.echo(f"\nEdite: {paths.env_path}")
        sys.exit(1)

    os.environ.setdefault("TEAM_NAME", name)

    if not use_tui:
        click.echo(f"Iniciando squad '{name}' (local, Ctrl+C para parar)...")
    daemon = Daemon(path_resolver=paths)

    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        if not use_tui:
            click.echo("\nSquad encerrada.")


@cli.command()
@click.argument("name", required=False)
@click.option("--all", "start_all", is_flag=True, help="Inicia todos os times.")
@click.option("--local", "force_local", is_flag=True, help="Força modo local.")
@click.option("--docker", "force_docker", is_flag=True, help="Força modo Docker.")
@click.option("--tui", "use_tui", is_flag=True, help="Usa interface TUI no terminal.")
def start(
    name: str | None, start_all: bool, force_local: bool, force_docker: bool, use_tui: bool
) -> None:
    """Inicia um time. Detecta automaticamente modo local ou Docker."""
    if force_local and force_docker:
        click.echo("Erro: Flags --local e --docker são mutuamente exclusivas.", err=True)
        sys.exit(1)

    manager = _get_manager()

    if start_all:
        teams = manager.list_teams()
        if not teams:
            click.echo("Nenhum time encontrado. Crie um com: ai-squad create")
            return
        for team in teams:
            _start_team(manager, team["name"])
        return

    if not name:
        click.echo("Informe o nome do time ou use --all.", err=True)
        sys.exit(1)

    # Determina modo
    if force_local:
        mode = "local"
    elif force_docker:
        mode = "docker"
    else:
        mode = _detect_mode(name)

    if mode == "local":
        _start_local(name, use_tui=use_tui)
    else:
        _start_team(manager, name)


def _start_team(manager: TeamManager, team_name: str) -> None:
    """Inicia um time específico."""
    if not manager.exists(team_name):
        click.echo(f"Erro: Time '{team_name}' não encontrado.", err=True)
        return

    # Valida .env
    missing = manager.validate_env(team_name)
    if missing:
        click.echo(f"Erro: Variáveis não preenchidas no .env de '{team_name}':")
        for var in missing:
            click.echo(f"  - {var}")
        click.echo(f"\nEdite: {manager.get_path(team_name) / '.env'}")
        return

    # Verifica se a imagem existe, constrói se necessário
    if not _image_exists():
        click.echo("Imagem ai-squad:latest não encontrada.")
        _build_image()

    team_dir = manager.get_path(team_name)
    click.echo(f"Iniciando time '{team_name}'...")

    resultado = subprocess.run(
        _docker_compose_cmd(team_dir, "up", "-d"),
        capture_output=True,
        text=True,
    )

    if resultado.returncode != 0:
        click.echo(f"Erro ao iniciar: {resultado.stderr}", err=True)
        return

    click.echo(f"Time '{team_name}' iniciado.")


@cli.command()
@click.argument("name", required=False)
@click.option("--all", "stop_all", is_flag=True, help="Para todos os times.")
def stop(name: str | None, stop_all: bool) -> None:
    """Para um time Docker. No modo local, use Ctrl+C."""
    # Verifica se é local
    local_dir = Path.cwd() / ".ai-squad"
    if local_dir.exists() and not stop_all:
        click.echo("Squad local roda em foreground — use Ctrl+C para parar.")
        return

    manager = _get_manager()

    if stop_all:
        teams = manager.list_teams()
        for team in teams:
            _stop_team(manager, team["name"])
        return

    if not name:
        click.echo("Informe o nome do time ou use --all.", err=True)
        sys.exit(1)

    _stop_team(manager, name)


def _stop_team(manager: TeamManager, team_name: str) -> None:
    """Para um time específico."""
    if not manager.exists(team_name):
        click.echo(f"Erro: Time '{team_name}' não encontrado.", err=True)
        return

    team_dir = manager.get_path(team_name)
    click.echo(f"Parando time '{team_name}'...")

    resultado = subprocess.run(
        _docker_compose_cmd(team_dir, "down"),
        capture_output=True,
        text=True,
    )

    if resultado.returncode != 0:
        click.echo(f"Erro ao parar: {resultado.stderr}", err=True)
        return

    click.echo(f"Time '{team_name}' parado.")


@cli.command()
@click.argument("name")
@click.confirmation_option(
    prompt="Tem certeza que deseja remover este time e todos os seus arquivos?"
)
def remove(name: str) -> None:
    """Remove um time e todos os seus arquivos."""
    from src.cli.team_manager import TeamNotFoundError

    # Verifica se é local
    local_dir = Path.cwd() / ".ai-squad"
    if local_dir.exists():
        shutil.rmtree(local_dir)
        click.echo("Squad local removida (.ai-squad/).")
        return

    manager = _get_manager()

    # Para o container se estiver rodando
    container_status = _get_container_status(name)
    if container_status == "running":
        click.echo(f"Parando container do time '{name}'...")
        team_dir = manager.get_path(name)
        subprocess.run(
            _docker_compose_cmd(team_dir, "down"),
            capture_output=True,
            text=True,
        )

    try:
        manager.remove(name)
        click.echo(f"Time '{name}' removido com sucesso.")
    except TeamNotFoundError as e:
        click.echo(f"Erro: {e}", err=True)
        sys.exit(1)


@cli.command("list")
def list_teams() -> None:
    """Lista times locais e Docker."""
    # Local
    local_dir = Path.cwd() / ".ai-squad"
    has_local = local_dir.exists()

    # Docker (global)
    manager = _get_manager()
    teams = manager.list_teams()

    if not has_local and not teams:
        click.echo("Nenhum time criado.")
        click.echo("Crie com: ai-squad create <nome>")
        return

    click.echo(f"{'Time':<20} {'Tipo':<10} {'Repo/Dir':<35} {'Status':<10}")
    click.echo("-" * 75)

    if has_local:
        click.echo(f"{'(local)':<20} {'local':<10} {str(Path.cwd()):<35} {'—':<10}")

    for team in teams:
        status = _get_container_status(team["name"])
        click.echo(f"{team['name']:<20} {'docker':<10} {team['repo_path']:<35} {status:<10}")


@cli.command()
@click.argument("name")
@click.option("--tail", default=0, help="Número de linhas finais a exibir.")
def logs(name: str, tail: int) -> None:
    """Exibe logs de um time."""
    manager = _get_manager()

    if not manager.exists(name):
        click.echo(f"Erro: Time '{name}' não encontrado.", err=True)
        sys.exit(1)

    team_dir = manager.get_path(name)
    cmd = _docker_compose_cmd(team_dir, "logs", "-f")
    if tail > 0:
        cmd.extend(["--tail", str(tail)])

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass


@cli.command()
@click.argument("name")
def status(name: str) -> None:
    """Exibe status das demandas ativas de um time."""
    manager = _get_manager()

    if not manager.exists(name):
        click.echo(f"Erro: Time '{name}' não encontrado.", err=True)
        sys.exit(1)

    container_status = _get_container_status(name)
    click.echo(f"Time: {name}")
    click.echo(f"Container: {container_status}")
    click.echo("")

    # Lê estado das demandas
    state_dir = manager.get_path(name) / "state"
    if not state_dir.exists() or not any(state_dir.iterdir()):
        click.echo("Nenhuma demanda registrada.")
        return

    import json

    click.echo(f"{'Demanda':<20} {'Estado':<25} {'Descrição':<35}")
    click.echo("-" * 80)

    for state_file in sorted(state_dir.glob("*.json")):
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            demand_id = data.get("demand_id", state_file.stem)
            state = data.get("state", "desconhecido")
            description = data.get("description", "")[:35]
            click.echo(f"{demand_id:<20} {state:<25} {description:<35}")
        except (json.JSONDecodeError, KeyError):
            continue


@cli.command()
def build() -> None:
    """Reconstrói a imagem Docker ai-squad:latest."""
    _build_image()


@cli.command("add-agent")
@click.argument("team_name")
@click.argument("agent_name")
@click.option("--name", "display_name", default=None, help="Nome de exibição do agente.")
@click.option("--avatar", default="🤖", help="Emoji avatar do agente.")
@click.option("--command", "cmd", default=None, help="Comando Telegram (ex: /sec).")
def add_agent(
    team_name: str,
    agent_name: str,
    display_name: str | None,
    avatar: str,
    cmd: str | None,
) -> None:
    """Adiciona um novo agente a um time existente."""
    manager = _get_manager()
    if not manager.exists(team_name):
        click.echo(f"Erro: Time '{team_name}' não encontrado.", err=True)
        sys.exit(1)

    team_dir = manager.get_path(team_name)
    agent_dir = team_dir / "agents" / agent_name

    if agent_dir.exists():
        click.echo(f"Erro: Agente '{agent_name}' já existe em '{team_name}'.", err=True)
        sys.exit(1)

    # Cria estrutura do agente
    agent_dir.mkdir(parents=True)
    (agent_dir / "skills").mkdir()

    display_name = display_name or agent_name.replace("-", " ").title()
    cmd = cmd or f"/{agent_name}"

    # Gera AGENTS.md template
    agents_md = f"""# {display_name}

## Dominio
<!-- Descreva o domínio de atuação deste agente -->

## Quando Envolver
- <!-- Quando o Squad Lead deve envolver este agente -->

## Responsabilidades
- <!-- Liste as responsabilidades -->

## Criterios de Aceite
- <!-- Liste os critérios verificáveis -->

## Restricoes
- <!-- Liste as restrições -->

## Instrucoes
<!-- Instruções detalhadas para o agente -->
"""
    (agent_dir / "AGENTS.md").write_text(agents_md, encoding="utf-8")
    (agent_dir / "CLAUDE.md").symlink_to("AGENTS.md")

    # Adiciona ao config.yaml
    import yaml

    config_path = team_dir / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if "agents" not in config:
        config["agents"] = {}

    config["agents"][agent_name] = {
        "name": display_name,
        "avatar": avatar,
        "command": cmd,
    }

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    click.echo(f"Agente '{agent_name}' adicionado ao time '{team_name}'.")
    click.echo(f"  Diretório: {agent_dir}")
    click.echo(f"  Comando: {cmd}")
    click.echo(f"  Edite: {agent_dir / 'AGENTS.md'}")
    click.echo(f"  Skills: {agent_dir / 'skills/'}")
    click.echo(
        f"\nReinicie o time para aplicar: ai-squad stop {team_name} && ai-squad start {team_name}"
    )


@cli.command("remove-agent")
@click.argument("team_name")
@click.argument("agent_name")
@click.confirmation_option(prompt="Tem certeza que deseja remover este agente?")
def remove_agent(team_name: str, agent_name: str) -> None:
    """Remove um agente de um time."""
    manager = _get_manager()
    if not manager.exists(team_name):
        click.echo(f"Erro: Time '{team_name}' não encontrado.", err=True)
        sys.exit(1)

    team_dir = manager.get_path(team_name)
    agent_dir = team_dir / "agents" / agent_name

    if not agent_dir.exists():
        click.echo(f"Erro: Agente '{agent_name}' não encontrado em '{team_name}'.", err=True)
        sys.exit(1)

    # Protege agentes obrigatórios
    if agent_name == "squad-lead":
        click.echo("Erro: Não é possível remover o Squad Lead.", err=True)
        sys.exit(1)

    # Remove diretório
    import shutil

    shutil.rmtree(agent_dir)

    # Remove do config.yaml
    import yaml

    config_path = team_dir / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if "agents" in config and agent_name in config["agents"]:
        del config["agents"][agent_name]
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    click.echo(f"Agente '{agent_name}' removido do time '{team_name}'.")


@cli.command("list-agents")
@click.argument("team_name")
def list_agents(team_name: str) -> None:
    """Lista os agentes de um time."""
    manager = _get_manager()
    if not manager.exists(team_name):
        click.echo(f"Erro: Time '{team_name}' não encontrado.", err=True)
        sys.exit(1)

    team_dir = manager.get_path(team_name)

    import yaml

    config_path = team_dir / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Squad Lead
    sl = config.get("squad_lead", {})
    click.echo(
        f"  {sl.get('avatar', '👨‍💼')} {sl.get('name', 'Squad Lead')} (squad-lead) — coordenador"
    )

    # Agentes
    agents = config.get("agents", {})
    for agent_id, agent_cfg in agents.items():
        has_skills = (team_dir / "agents" / agent_id / "skills").exists()
        skills_count = 0
        if has_skills:
            skills_dir = team_dir / "agents" / agent_id / "skills"
            skills_count = (
                len([d for d in skills_dir.iterdir() if d.is_dir()]) if skills_dir.exists() else 0
            )
        skills_label = f" ({skills_count} skills)" if skills_count else ""
        click.echo(
            f"  {agent_cfg.get('avatar', '🤖')} {agent_cfg.get('name', agent_id)} "
            f"({agent_id}) — {agent_cfg.get('command', '/' + agent_id)}{skills_label}"
        )


@cli.command()
def generate() -> None:
    """Cria um time via IA a partir de uma descrição em linguagem natural."""
    from src.cli.generate import generate_team
    from src.cli.wizard import GenerateWizard

    wizard = GenerateWizard()

    try:
        result = wizard.run()
    except click.Abort:
        click.echo("\nGeração cancelada.")
        return

    try:
        generate_team(result)
    except SystemExit:
        return
    except Exception as e:
        click.echo(f"\nErro na geração: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
