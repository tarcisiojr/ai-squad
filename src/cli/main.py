"""CLI principal do ai-dev-team."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import click

from src.cli.team_manager import (
    InvalidEnvError,
    TeamExistsError,
    TeamManager,
    TeamNotFoundError,
)


def _get_manager() -> TeamManager:
    """Retorna instância do TeamManager."""
    return TeamManager()


def _docker_compose_cmd(team_dir: Path, *args: str) -> list[str]:
    """Monta comando docker compose para um time."""
    return [
        "docker", "compose",
        "-f", str(team_dir / "docker-compose.yml"),
        *args,
    ]


def _image_exists() -> bool:
    """Verifica se a imagem ai-dev-team:latest existe."""
    resultado = subprocess.run(
        ["docker", "image", "inspect", "ai-dev-team:latest"],
        capture_output=True,
        text=True,
    )
    return resultado.returncode == 0


def _build_image() -> None:
    """Constrói a imagem Docker ai-dev-team:latest.

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

        click.echo("Construindo imagem ai-dev-team:latest...")
        resultado = subprocess.run(
            ["docker", "build", "-t", "ai-dev-team:latest", str(tmp_path)],
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
        ([sys.executable, "-m", "build", "--wheel", "--outdir", str(output_dir), str(source_dir)], "python -m build"),
        ([sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(output_dir), str(source_dir)], "pip wheel"),
    ]

    for cmd, name in build_commands:
        resultado = subprocess.run(cmd, capture_output=True, text=True)
        if resultado.returncode == 0:
            whl_files = list(output_dir.glob("*.whl"))
            if whl_files:
                click.echo(f"  .whl gerado via {name}: {whl_files[0].name}")
                return True

    click.echo(
        "Erro: não foi possível gerar o .whl.\n"
        "Instale 'uv' ou 'build': pip install build",
        err=True,
    )
    return False


def _find_source_dir() -> Path:
    """Localiza diretório com código-fonte do ai-dev-team (com pyproject.toml)."""
    source_ref = Path.home() / ".ai-dev-team" / "source_path"

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
        "Erro: código-fonte do ai-dev-team não encontrado.\n"
        "Execute 'ai-dev-team build' uma vez de dentro do diretório do projeto,\n"
        "ou crie o arquivo ~/.ai-dev-team/source_path com o caminho do projeto.",
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
@click.version_option(version="0.1.0", prog_name="ai-dev-team")
def cli() -> None:
    """ai-dev-team — Time completo de desenvolvimento autônomo por IA."""
    pass


@cli.command()
@click.argument("name")
@click.option("--repo", required=True, help="Caminho do repositório alvo.")
def create(name: str, repo: str) -> None:
    """Cria um novo time de desenvolvimento."""
    manager = _get_manager()
    try:
        team_dir = manager.create(name, repo)
        click.echo(f"Time '{name}' criado em {team_dir}")
        click.echo("")
        click.echo("Próximos passos:")
        click.echo(f"  1. Edite o .env: {team_dir / '.env'}")
        click.echo(f"  2. Inicie o time: ai-dev-team start {name}")
    except FileNotFoundError as e:
        click.echo(f"Erro: {e}", err=True)
        sys.exit(1)
    except TeamExistsError as e:
        click.echo(f"Erro: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("name", required=False)
@click.option("--all", "start_all", is_flag=True, help="Inicia todos os times.")
def start(name: str | None, start_all: bool) -> None:
    """Inicia um time (sobe o container Docker)."""
    manager = _get_manager()

    if start_all:
        teams = manager.list_teams()
        if not teams:
            click.echo("Nenhum time encontrado. Crie um com: ai-dev-team create")
            return
        for team in teams:
            _start_team(manager, team["name"])
        return

    if not name:
        click.echo("Informe o nome do time ou use --all.", err=True)
        sys.exit(1)

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
        click.echo("Imagem ai-dev-team:latest não encontrada.")
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
    """Para um time (derruba o container Docker)."""
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


@cli.command("list")
def list_teams() -> None:
    """Lista todos os times e seus status."""
    manager = _get_manager()
    teams = manager.list_teams()

    if not teams:
        click.echo("Nenhum time criado.")
        click.echo("Crie um com: ai-dev-team create <nome> --repo <caminho>")
        return

    # Cabeçalho da tabela
    click.echo(f"{'Time':<20} {'Repo':<40} {'Status':<10}")
    click.echo("-" * 70)

    for team in teams:
        status = _get_container_status(team["name"])
        click.echo(f"{team['name']:<20} {team['repo_path']:<40} {status:<10}")


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
    """Reconstrói a imagem Docker ai-dev-team:latest."""
    _build_image()


if __name__ == "__main__":
    cli()
