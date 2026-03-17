"""Verificação de artefatos e conclusão de agentes.

Lógica de validação extraída do engine para desacoplamento.
Hoje verifica artefatos OpenSpec; na Fase 3 será substituído por
quality gates declarativos nos step files.
"""

import logging
import re
from pathlib import Path

from src.orchestrator.tools import VerificationResult

logger = logging.getLogger("ai-dev-team.verification")

# Tamanho minimo em bytes para considerar um artefato valido
MIN_ARTIFACT_SIZE = 50


def classify_agent_role(agent_name: str, agents_dir: Path, role_override: str = "") -> str:
    """Classifica o papel de um agente baseado no AGENTS.md.

    Se role_override estiver definido (via config), usa direto sem inferir.
    Retorna: 'spec', 'dev', 'review', ou 'generic'.
    """
    # Se role está definido na config, usa direto
    if role_override:
        return role_override

    agents_md = _read_agents_md(agent_name, agents_dir).lower()

    if "openspec" in agents_md and ("proposal" in agents_md or "specs" in agents_md):
        return "spec"
    if "tasks.md" in agents_md and (
        "implemente" in agents_md or "codigo" in agents_md or "commit" in agents_md
    ):
        return "dev"
    if "aprovado" in agents_md and (
        "rejeitado" in agents_md or "review" in agents_md or "validar" in agents_md
    ):
        return "review"

    return "generic"


def verify_completion(
    agent_name: str,
    resultado: str,
    workspace: str,
    agents_dir: Path,
    running_agents: dict,
    role_override: str = "",
) -> VerificationResult:
    """Verifica conclusão de agente via artefatos reais.

    Classificação dinâmica: detecta o papel pelo AGENTS.md
    em vez de hardcodar nomes. Se role_override definido, usa direto.
    """
    role = classify_agent_role(agent_name, agents_dir, role_override)
    issues: list[str] = []

    if role == "spec":
        issues = _verify_spec_completion(workspace)
    elif role == "dev":
        issues = _verify_dev_completion(workspace, agents_dir, running_agents)
    elif role == "review":
        issues = _verify_review_completion(resultado)

    if issues:
        return VerificationResult(passed=False, details="; ".join(issues))

    return VerificationResult(passed=True, details="Todas as verificacoes passaram")


def collect_artifact_issues(change_dir: Path) -> list[dict]:
    """Coleta problemas em artefatos de uma change.

    Retorna lista de checks com {name, passed, detail}.
    Usado por verificação interna e por check_artifacts (MCP tool).
    """
    checks: list[dict] = []

    # Verifica arquivos obrigatórios
    for filename in ("proposal.md", "design.md", "tasks.md"):
        filepath = change_dir / filename
        exists = filepath.exists()
        size_ok = False
        if exists:
            try:
                size_ok = filepath.stat().st_size >= MIN_ARTIFACT_SIZE
            except OSError:
                pass
        checks.append({
            "name": f"{filename.replace('.md', '')}_exists",
            "passed": exists and size_ok,
            "detail": (
                f"{filename} encontrado" if exists and size_ok
                else f"{filename} ausente" if not exists
                else f"{filename} parece vazio"
            ),
        })

    # Verifica specs com critérios de aceite
    specs_dir = change_dir / "specs"
    spec_files = list(specs_dir.rglob("*.md")) if specs_dir.exists() else []
    checks.append({
        "name": "specs_exist",
        "passed": len(spec_files) > 0,
        "detail": (
            f"{len(spec_files)} spec(s) encontrada(s)"
            if spec_files else "Nenhuma spec encontrada"
        ),
    })

    for spec_file in spec_files:
        try:
            content = spec_file.read_text(encoding="utf-8")
            has_criteria = "- [ ]" in content or "- [x]" in content
            rel_path = spec_file.relative_to(specs_dir)
            checks.append({
                "name": f"spec_criteria_{rel_path}",
                "passed": has_criteria,
                "detail": (
                    f"specs/{rel_path} tem criterios de aceite" if has_criteria
                    else f"specs/{rel_path} NAO tem criterios de aceite (adicione checklist '- [ ]')"
                ),
            })
        except (OSError, UnicodeDecodeError):
            pass

    # Verifica tasks com mínimo de itens
    tasks_file = change_dir / "tasks.md"
    if tasks_file.exists():
        try:
            content = tasks_file.read_text(encoding="utf-8")
            pending = len(re.findall(r"- \[ \]", content))
            done = len(re.findall(r"- \[x\]", content))
            total = pending + done
            checks.append({
                "name": "tasks_minimum",
                "passed": total >= 3,
                "detail": (
                    f"tasks.md tem {total} itens ({done} concluidos, {pending} pendentes)"
                    if total >= 3
                    else f"tasks.md tem apenas {total} itens (minimo 3)"
                ),
            })
        except (OSError, UnicodeDecodeError):
            checks.append({
                "name": "tasks_minimum",
                "passed": False,
                "detail": "Erro ao ler tasks.md",
            })

    return checks


def check_artifacts_enriched(change_name: str, workspace: str) -> str:
    """Verifica artefatos openspec com validação de qualidade (Criteria Gate).

    Retorna string formatada com resultado detalhado.
    """
    ws = Path(workspace)
    change_dir = ws / "openspec" / "changes" / change_name

    if not change_dir.exists():
        return f"Change '{change_name}' nao encontrada."

    checks = collect_artifact_issues(change_dir)

    passed = all(c["passed"] for c in checks)
    total_checks = len(checks)
    passed_checks = sum(1 for c in checks if c["passed"])

    lines = [f"Verificacao de artefatos: {change_name}"]
    lines.append(
        f"Resultado: {'APROVADO' if passed else 'REPROVADO'} ({passed_checks}/{total_checks})"
    )
    lines.append("")
    for c in checks:
        status = "OK" if c["passed"] else "FALHA"
        lines.append(f"  [{status}] {c['detail']}")

    if not passed:
        failed = [c for c in checks if not c["passed"]]
        lines.append("")
        lines.append("Acao necessaria:")
        for c in failed:
            lines.append(f"  - Corrigir: {c['detail']}")

    return "\n".join(lines)


def _read_agents_md(agent_name: str, agents_dir: Path) -> str:
    """Lê o AGENTS.md de um agente."""
    path = agents_dir / agent_name / "AGENTS.md"
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _verify_spec_completion(workspace: str) -> list[str]:
    """Verifica artefatos openspec — usa collect_artifact_issues."""
    ws = Path(workspace)
    changes_dir = ws / "openspec" / "changes"

    if not changes_dir.exists():
        return ["Diretorio openspec/changes nao encontrado"]

    active_changes = [
        d for d in changes_dir.iterdir()
        if d.is_dir() and d.name != "archive"
    ]
    if not active_changes:
        return ["Nenhuma change ativa encontrada"]

    checks = collect_artifact_issues(active_changes[-1])
    return [c["detail"] for c in checks if not c["passed"]]


def _verify_dev_completion(
    workspace: str, agents_dir: Path, running_agents: dict,
) -> list[str]:
    """Verifica se Dev concluiu.

    Multi-dev awareness: se outro dev está rodando, aceita conclusão parcial.
    """
    dev_agents_running = [
        name for name, ra in running_agents.items()
        if ra.status == "running" and classify_agent_role(name, agents_dir) == "dev"
    ]
    if dev_agents_running:
        return []

    issues: list[str] = []
    tasks_check = _check_tasks_md_completion(workspace)
    if tasks_check:
        issues.append(tasks_check)
    return issues


def _verify_review_completion(resultado: str) -> list[str]:
    """Verifica se agente de revisão concluiu com veredicto."""
    resultado_lower = resultado.lower()
    has_verdict = any(
        word in resultado_lower
        for word in ("aprovado", "approved", "rejeitado", "rejected")
    )
    if not has_verdict:
        return ["Resultado nao contem veredicto ('APROVADO' ou 'REJEITADO')"]
    return []


def _check_tasks_md_completion(workspace: str) -> str | None:
    """Verifica se tasks.md tem itens pendentes."""
    ws = Path(workspace)
    changes_dir = ws / "openspec" / "changes"
    if not changes_dir.exists():
        return None

    for change_dir in changes_dir.iterdir():
        if not change_dir.is_dir() or change_dir.name == "archive":
            continue
        tasks_file = change_dir / "tasks.md"
        if not tasks_file.exists():
            continue
        try:
            content = tasks_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        pending = len(re.findall(r"- \[ \]", content))
        done = len(re.findall(r"- \[x\]", content))
        total = pending + done

        if pending > 0:
            return f"tasks.md ({change_dir.name}): {pending}/{total} tasks pendentes"

    return None
