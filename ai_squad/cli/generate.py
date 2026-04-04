"""Lógica de geração e criação de estrutura do time."""

import json
import re
from pathlib import Path
from typing import Any

import click
import yaml

from ai_squad.cli.generators.interface import get_provider, get_provider_config
from ai_squad.cli.generators.prompt import build_generation_prompt
from ai_squad.cli.wizard import WizardResult


def generate_team(result: WizardResult) -> Path:
    """Gera e cria a estrutura completa do time.

    Args:
        result: Dados coletados pelo wizard.

    Returns:
        Caminho do diretório .ai-squad/ criado.
    """
    # Gera via IA
    click.echo("\n⏳ Gerando pipeline e agentes com IA...")

    provider = get_provider(result.provider, result.token)
    prompt = build_generation_prompt(result.description)
    raw_response = provider.generate(prompt)

    # Parseia o JSON da resposta
    generated = _parse_response(raw_response)

    # Cria a estrutura de diretórios
    squad_dir = Path.cwd() / ".ai-squad"
    _create_structure(squad_dir, generated, result)

    # Exibe resumo
    _show_summary(generated, result.team_name)

    return squad_dir


def _parse_response(raw: str) -> dict[str, Any]:
    """Extrai JSON da resposta da IA."""
    # Remove blocos de código markdown se presentes
    cleaned = re.sub(r"```(?:json)?\s*", "", raw)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Tenta encontrar JSON dentro do texto
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        click.echo(
            "Erro: não foi possível interpretar a resposta da IA.\n"
            "Tente novamente com uma descrição mais detalhada.",
            err=True,
        )
        raise SystemExit(1)


def _create_structure(squad_dir: Path, generated: dict[str, Any], result: WizardResult) -> None:
    """Cria todos os diretórios e arquivos do time."""
    squad_dir.mkdir(parents=True)
    (squad_dir / "state").mkdir()

    # Pipeline
    _write_pipeline(squad_dir, generated)

    # Step files
    _write_steps(squad_dir, generated)

    # Agents
    _write_agents(squad_dir, generated)

    # Config.yaml
    _write_config(squad_dir, generated, result)

    # .env com tokens reais
    _write_env(squad_dir, result)

    # Knowledge base
    if result.knowledge_enabled:
        (squad_dir / "knowledge").mkdir()


def _write_pipeline(squad_dir: Path, generated: dict[str, Any]) -> None:
    """Escreve pipeline/pipeline.yaml."""
    pipeline_dir = squad_dir / "pipeline"
    pipeline_dir.mkdir()
    (pipeline_dir / "steps").mkdir()

    pipeline_data: dict[str, Any] = generated.get("pipeline", {})
    pipeline_path = pipeline_dir / "pipeline.yaml"
    pipeline_path.write_text(
        yaml.dump(pipeline_data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _write_steps(squad_dir: Path, generated: dict[str, Any]) -> None:
    """Escreve os step files em pipeline/steps/."""
    steps_dir = squad_dir / "pipeline" / "steps"
    steps: dict[str, str] = generated.get("steps", {})

    for filename, content in steps.items():
        # Normaliza o caminho (pode vir como "steps/step-01-nome.md")
        name = Path(filename).name
        step_path = steps_dir / name
        step_path.write_text(content, encoding="utf-8")


def _write_agents(squad_dir: Path, generated: dict[str, Any]) -> None:
    """Escreve AGENTS.md para cada agente."""
    agents: dict[str, dict[str, Any]] = generated.get("agents", {})

    for agent_name, agent_data in agents.items():
        agent_dir = squad_dir / "agents" / agent_name
        agent_dir.mkdir(parents=True)

        agents_md: str = agent_data.get("agents_md", f"# {agent_data.get('display_name', agent_name)}\n")
        (agent_dir / "AGENTS.md").write_text(agents_md, encoding="utf-8")

    # Squad Lead (sempre obrigatório)
    sl_dir = squad_dir / "agents" / "squad-lead"
    sl_dir.mkdir(parents=True, exist_ok=True)

    squad_lead_md: str = generated.get("squad_lead_md", _default_squad_lead_md())
    (sl_dir / "AGENTS.md").write_text(squad_lead_md, encoding="utf-8")


def _write_config(squad_dir: Path, generated: dict[str, Any], result: WizardResult) -> None:
    """Gera config.yaml com agents e configuração do time."""
    provider_config = get_provider_config(result.provider)
    agents = generated.get("agents", {})

    config: dict[str, Any] = {
        "ai_provider": provider_config.ai_provider,
        "messaging_provider": result.messaging,
        "ai_model": "claude-sonnet-4-20250514",
        "agent_timeout": 300,
        "squad_lead": {"name": "Squad Lead", "avatar": "👨‍💼"},
        "agents": {},
    }

    for agent_name, agent_data in agents.items():
        config["agents"][agent_name] = {
            "name": agent_data.get("display_name", agent_name.replace("-", " ").title()),
            "avatar": agent_data.get("avatar", "🤖"),
            "command": f"/{agent_name}",
        }

    if result.knowledge_enabled:
        config["knowledge"] = {
            "enabled": True,
            "use_qmd": False,
            "knowledge_dir": "knowledge/",
        }

    config_path = squad_dir / "config.yaml"
    config_path.write_text(
        yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _write_env(squad_dir: Path, result: WizardResult) -> None:
    """Gera .env com tokens reais (sem placeholders)."""
    provider_config = get_provider_config(result.provider)

    lines = ["# === Tokens obrigatórios ===\n"]

    # Token do provider de IA (pula se env_var vazio, ex: copilot)
    if provider_config.env_var:
        lines.append(f"# Token do provider de IA ({result.provider})")
        lines.append(f"{provider_config.env_var}={result.token}\n")
    elif result.token:
        # Copilot com GITHUB_TOKEN informado opcionalmente
        lines.append("# Token GitHub (opcional para Copilot)")
        lines.append(f"GITHUB_TOKEN={result.token}\n")
    else:
        lines.append("# Copilot: autenticação via 'copilot auth login'")
        lines.append("# GITHUB_TOKEN=\n")

    # Credenciais do canal
    if result.channel_credentials:
        lines.append(f"# === {result.messaging.upper()} ===\n")
        for var, value in result.channel_credentials.items():
            lines.append(f"{var}={value}")
        lines.append("")

    # Opcionais
    lines.append("# === Opcional ===\n")
    lines.append("# GitHub (para criar PRs e push)")
    lines.append("# GITHUB_TOKEN=\n")

    env_path = squad_dir / ".env"
    env_path.write_text("\n".join(lines), encoding="utf-8")


def _show_summary(generated: dict[str, Any], team_name: str) -> None:
    """Exibe resumo do time gerado."""
    agents = generated.get("agents", {})
    pipeline = generated.get("pipeline", {})
    steps = pipeline.get("steps", [])

    agent_names = list(agents.keys())
    checkpoints = [s for s in steps if s.get("type") == "checkpoint"]
    step_names = [s.get("name", s.get("id", "?")) for s in steps]

    click.echo(f'\n✅ Time "{team_name}" criado em .ai-squad/\n')
    click.echo(f"  Agentes: {', '.join(agent_names)}")
    click.echo(f"  Pipeline: {' → '.join(step_names)}")
    click.echo(f"  Checkpoints: {len(checkpoints)}")
    click.echo(f"\n  Para iniciar: ai-squad start {team_name}")


def _default_squad_lead_md() -> str:
    """AGENTS.md padrão para o Squad Lead."""
    return """\
# Squad Lead

## Dominio
Coordenação e liderança do time.

## Quando Envolver
- Sempre — o Squad Lead é o agente obrigatório que coordena todos os demais

## Responsabilidades
- Classificar a intenção do usuário antes de agir
- Consultar estado das demandas antes de decidir
- Delegar trabalho via start_agent
- Manter o usuário informado sobre o progresso

## Restricoes
- NÃO implemente código diretamente
- NÃO execute o trabalho de outro agente
- SEMPRE delegue ao agente especializado

## Instrucoes
Você é o líder técnico. Classifique a mensagem do usuário, consulte o estado \
das demandas e delegue ao agente correto.

## Comunicacao
- Respostas curtas e diretas
- Português brasileiro
- Informe o que FEZ, não o que pretende fazer
"""
