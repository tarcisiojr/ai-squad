"""Tools disponíveis para o Squad Lead invocar agentes e verificar status."""

import asyncio
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AgentResult:
    """Resultado da execução de um agente."""

    agent_name: str
    result: str
    success: bool = True
    error: str = ""


@dataclass
class VerificationResult:
    """Resultado da verificacao de conclusao de um agente."""

    passed: bool
    details: str


@dataclass
class RunningAgent:
    """Agente em execucao background."""

    agent_name: str
    demand_id: str
    user_id: str = ""
    task: asyncio.Task | None = None
    started_at: float = field(default_factory=time.time)
    status: str = "running"  # running, done, error, incomplete
    result: str | None = None
    error: str | None = None
    retries: int = 0

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_at

    def elapsed_str(self) -> str:
        secs = int(self.elapsed)
        if secs < 60:
            return f"{secs}s"
        mins = secs // 60
        rest = secs % 60
        if rest:
            return f"{mins}min{rest}s"
        return f"{mins}min"


@dataclass
class DemandStatus:
    """Status de uma demanda em andamento."""

    demand_id: str
    results: dict[str, AgentResult] = field(default_factory=dict)

    def set_result(self, agent_name: str, result: AgentResult) -> None:
        self.results[agent_name] = result

    def get_summary(self) -> str:
        """Retorna resumo textual do status."""
        if not self.results:
            return "Nenhum agente executado ainda."

        lines = [f"Status da demanda {self.demand_id}:\n"]
        for name, res in self.results.items():
            status = "Concluido" if res.success else f"Erro: {res.error}"
            preview = res.result[:100] + "..." if len(res.result) > 100 else res.result
            lines.append(f"- {name}: {status}")
            if res.result:
                lines.append(f"  Resultado: {preview}")

        return "\n".join(lines)


def check_workspace(workspace: str = "/workspace") -> str:
    """Verifica mudancas no workspace via git."""
    ws = Path(workspace)
    if not ws.exists():
        return "Workspace nao encontrado."

    parts = []

    # git status
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            cwd=str(ws),
            timeout=10,
        )
        status = result.stdout.strip()
        parts.append(f"Git status:\n{status if status else '(limpo, sem mudancas)'}")
    except Exception as e:
        parts.append(f"Git status: erro - {e}")

    # git log ultimos commits
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            capture_output=True,
            text=True,
            cwd=str(ws),
            timeout=10,
        )
        log = result.stdout.strip()
        if log:
            parts.append(f"\nUltimos commits:\n{log}")
    except Exception:
        pass

    return "\n".join(parts)
