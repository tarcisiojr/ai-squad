"""Funções para construção de prompts dos agentes."""

from pathlib import Path

from src.orchestrator.journal import JournalStore
from src.orchestrator.state import StateManager


def _get_agent_label(agent_name: str, personas: dict) -> str:
    """Retorna label do agente a partir das personas da config."""
    persona = personas.get(agent_name)
    if persona:
        return f"{persona.avatar} {persona.name}"
    return agent_name


def read_agents_md(agent_name: str, agents_dir: Path) -> str:
    """Le o AGENTS.md de um agente."""
    path = agents_dir / agent_name / "AGENTS.md"
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def get_agents_summary(personas: dict, agents_dir: Path) -> str:
    """Gera resumo de todos os agentes para o prompt do Squad Lead."""
    lines = ["## Agentes disponiveis\n"]

    for agent_id, config in personas.items():
        agents_md = read_agents_md(agent_id, agents_dir)

        dominio = ""
        quando = ""
        criterios = ""
        current_section = ""

        for line in agents_md.splitlines():
            if line.startswith("## Dominio"):
                current_section = "dominio"
            elif line.startswith("## Quando Envolver"):
                current_section = "quando"
            elif line.startswith("## Criterios de Aceite"):
                current_section = "criterios"
            elif line.startswith("## "):
                current_section = ""
            elif current_section == "dominio" and line.strip():
                dominio += line.strip() + " "
            elif current_section == "quando" and line.strip():
                quando += line + "\n"
            elif current_section == "criterios" and line.strip():
                criterios += line + "\n"

        lines.append(f"### {config.avatar} {config.name} ({agent_id})")
        if dominio:
            lines.append(f"Dominio: {dominio.strip()}")
        if quando:
            lines.append(f"Quando envolver:\n{quando.strip()}")
        if criterios:
            lines.append(f"Criterios de aceite:\n{criterios.strip()}")
        if hasattr(config, "submodules") and config.submodules:
            subs = ", ".join(
                f"{s.path}" + (f" ({s.description})" if s.description else "")
                for s in config.submodules
            )
            lines.append(f"Submodulos: {subs}")
        lines.append("")

    return "\n".join(lines)


def get_running_agents_status(running_agents: dict, personas: dict) -> str:
    """Retorna status formatado de todos os agentes, agrupados por demanda."""
    if not running_agents:
        return "Nenhum agente ativo no momento."

    # Agrupa agentes por demand_id
    by_demand: dict[str, list[tuple[str, object]]] = {}
    for name, ra in running_agents.items():
        demand_id = ra.demand_id or "sem-demanda"
        by_demand.setdefault(demand_id, []).append((name, ra))

    lines = []
    for demand_id, agents in by_demand.items():
        lines.append(f"**Demanda: {demand_id}**")
        for name, ra in agents:
            label = _get_agent_label(name, personas)
            elapsed = ra.elapsed_str()

            if ra.status == "running":
                lines.append(f"  - {label}: rodando ({elapsed})")
            elif ra.status == "done":
                preview = (ra.result or "")[:300]
                if preview:
                    preview = f" — {preview}"
                lines.append(f"  - {label}: concluido ({elapsed}){preview}")
            elif ra.status == "error":
                lines.append(f"  - {label}: erro ({elapsed}) — {ra.error}")

    return "\n".join(lines)


def get_demand_state_summary(
    journal: JournalStore,
    state_manager: StateManager,
    running_agents: dict,
    personas: dict,
) -> str:
    """Retorna resumo do estado de todas as demandas ativas.

    Genérico — não assume nomes de fase específicos.
    A fase vem do journal (current_phase) e pode ser qualquer string
    definida pelo pipeline ou pelo Squad Lead.
    """
    active_journals = journal.get_active_journals()

    if not active_journals:
        try:
            pending = state_manager.get_pending_demands()
            if not pending:
                return "Nenhuma demanda ativa."
            lines = ["Demandas ativas:"]
            for d in pending:
                state = d.get("state", "?")
                lines.append(f"  - {d['demand_id']}: {state}")
            return "\n".join(lines)
        except Exception:
            return "Nenhuma demanda ativa."

    lines = [f"{len(active_journals)} demanda(s) ativa(s):\n"]
    for j in active_journals:
        demand_id = j.get("demand_id", "?")
        demand_text = j.get("demand_text", "?")
        phase = j.get("current_phase", "?")
        next_expected = j.get("next_expected")

        lines.append(f"### {demand_id}")
        lines.append(f"  Demanda: {demand_text}")
        lines.append(f"  Fase: {phase}")
        if next_expected:
            desc = next_expected.get("description", "")
            agent = next_expected.get("agent", "")
            if desc:
                lines.append(f"  Proximo: {desc}")
            if agent:
                label = _get_agent_label(agent, personas)
                lines.append(f"  Agente esperado: {label}")

        # Agentes rodando para esta demanda
        running = [
            ra
            for ra in running_agents.values()
            if ra.demand_id == demand_id and ra.status == "running"
        ]
        if running:
            for ra in running:
                label = _get_agent_label(ra.agent_name, personas)
                lines.append(f"  Agente ativo: {label} ({ra.elapsed_str()})")
        lines.append("")

    return "\n".join(lines)
