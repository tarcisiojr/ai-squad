"""Estado e execução de pipelines declarativos.

Gerencia o ciclo de vida de demandas através de steps definidos
em pipeline.yaml, com persistência em pipeline-state.json.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.orchestrator.atomic_write import write_json_atomic
from src.orchestrator.pipeline import PipelineConfig, StepConfig

logger = logging.getLogger("ai-squad.pipeline-state")


@dataclass
class StepState:
    """Estado de um step individual."""

    step_id: str
    name: str
    status: str = "pending"  # pending, running, checkpoint, completed, failed, skipped
    agents: list[str] = field(default_factory=list)
    agent_status: dict[str, str] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    quality_gate_result: str = ""  # passed, failed, skipped
    review_cycle: int = 0
    review_history: list[dict] = field(default_factory=list)
    retries: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        """Serializa para JSON."""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "status": self.status,
            "agents": self.agents,
            "agent_status": self.agent_status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "quality_gate_result": self.quality_gate_result,
            "review_cycle": self.review_cycle,
            "review_history": self.review_history,
            "retries": self.retries,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StepState":
        """Deserializa de JSON."""
        return cls(
            step_id=data.get("step_id", ""),
            name=data.get("name", ""),
            status=data.get("status", "pending"),
            agents=data.get("agents", []),
            agent_status=data.get("agent_status", {}),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
            quality_gate_result=data.get("quality_gate_result", ""),
            review_cycle=data.get("review_cycle", 0),
            review_history=data.get("review_history", []),
            retries=data.get("retries", 0),
            error=data.get("error", ""),
        )


@dataclass
class PipelineState:
    """Estado completo do pipeline para uma demanda."""

    demand_id: str
    pipeline_name: str = ""
    status: str = "idle"  # idle, running, completed, failed, paused
    current_step: str = ""
    started_at: str = ""
    updated_at: str = ""
    steps: dict[str, StepState] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serializa para JSON."""
        return {
            "demand_id": self.demand_id,
            "pipeline_name": self.pipeline_name,
            "status": self.status,
            "current_step": self.current_step,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "steps": {k: v.to_dict() for k, v in self.steps.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineState":
        """Deserializa de JSON."""
        steps = {}
        for step_id, step_data in data.get("steps", {}).items():
            steps[step_id] = StepState.from_dict(step_data)

        return cls(
            demand_id=data.get("demand_id", ""),
            pipeline_name=data.get("pipeline_name", ""),
            status=data.get("status", "idle"),
            current_step=data.get("current_step", ""),
            started_at=data.get("started_at", ""),
            updated_at=data.get("updated_at", ""),
            steps=steps,
        )

    def get_step_state(self, step_id: str) -> StepState | None:
        """Retorna estado de um step."""
        return self.steps.get(step_id)


class PipelineExecutor:
    """Gerencia execução de pipeline declarativo para uma ou mais demandas.

    Responsabilidades:
    - Iniciar pipeline para nova demanda
    - Avançar entre steps automaticamente
    - Pausar em checkpoints
    - Suportar loops on_reject
    - Persistir estado
    - Formatar estado para prompt do Squad Lead
    """

    def __init__(self, state_dir: str | Path, pipeline: PipelineConfig) -> None:
        self._state_dir = Path(state_dir)
        self._pipeline = pipeline
        # Cache de estados em memória
        self._states: dict[str, PipelineState] = {}

    @staticmethod
    def _now() -> str:
        """Timestamp ISO-8601 UTC."""
        return datetime.now(timezone.utc).isoformat()

    def _state_path(self, demand_id: str) -> Path:
        """Caminho do arquivo de estado do pipeline."""
        demand_dir = self._state_dir / demand_id
        demand_dir.mkdir(parents=True, exist_ok=True)
        return demand_dir / "pipeline-state.json"

    def _save_state(self, state: PipelineState) -> None:
        """Persiste estado do pipeline."""
        state.updated_at = self._now()
        path = self._state_path(state.demand_id)
        write_json_atomic(path, state.to_dict())
        self._states[state.demand_id] = state

    def load_state(self, demand_id: str) -> PipelineState | None:
        """Carrega estado persistido de uma demanda."""
        if demand_id in self._states:
            return self._states[demand_id]

        path = self._state_path(demand_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            state = PipelineState.from_dict(data)
            self._states[demand_id] = state
            return state
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Erro ao carregar pipeline state: %s", e)
            return None

    def start_pipeline(self, demand_id: str) -> PipelineState:
        """Inicia pipeline para uma nova demanda.

        Cria estado inicial com todos os steps em 'pending'
        e marca o primeiro step como 'running'.
        """
        state = PipelineState(
            demand_id=demand_id,
            pipeline_name=self._pipeline.name,
            status="running",
            started_at=self._now(),
        )

        # Inicializa estado de cada step
        for step in self._pipeline.steps:
            state.steps[step.id] = StepState(
                step_id=step.id,
                name=step.name,
                agents=step.all_agents,
            )

        # Marca primeiro step como ativo
        first = self._pipeline.first_step
        if first:
            state.current_step = first.id
            step_state = state.steps[first.id]
            step_state.status = "running"
            step_state.started_at = self._now()

        self._save_state(state)
        logger.info("Pipeline iniciado: %s (demand: %s)", self._pipeline.name, demand_id)
        return state

    def get_current_step(self, demand_id: str) -> StepConfig | None:
        """Retorna config do step atual da demanda."""
        state = self.load_state(demand_id)
        if not state or not state.current_step:
            return None
        return self._pipeline.get_step(state.current_step)

    def complete_step(
        self,
        demand_id: str,
        step_id: str,
        quality_gate_result: str = "passed",
    ) -> StepConfig | None:
        """Marca step como completo e retorna próximo step (ou None se pipeline concluiu).

        Se quality gate falhou, marca como failed e NÃO avança.
        """
        state = self.load_state(demand_id)
        if not state:
            return None

        step_state = state.steps.get(step_id)
        if not step_state:
            return None

        step_state.quality_gate_result = quality_gate_result
        step_state.completed_at = self._now()

        if quality_gate_result == "passed":
            step_state.status = "completed"
            # Avança para próximo step
            return self._advance_to_next(state, step_id)
        else:
            step_state.status = "failed"
            step_state.retries += 1
            self._save_state(state)
            return None

    def _advance_to_next(
        self,
        state: PipelineState,
        current_step_id: str,
    ) -> StepConfig | None:
        """Avança pipeline para o próximo step."""
        next_step = self._pipeline.next_step(current_step_id)

        if next_step is None:
            # Pipeline concluiu
            state.status = "completed"
            state.current_step = ""
            self._save_state(state)
            logger.info("Pipeline concluido: %s", state.demand_id)
            return None

        # Ativa próximo step
        state.current_step = next_step.id
        next_state = state.steps.get(next_step.id)
        if next_state:
            if next_step.is_checkpoint:
                next_state.status = "checkpoint"
            else:
                next_state.status = "running"
            next_state.started_at = self._now()

        self._save_state(state)
        return next_step

    def handle_reject(self, demand_id: str, step_id: str, feedback: str) -> str | None:
        """Trata rejeição de um step com on_reject.

        Retorna step_id destino do loop, ou None se max_review_cycles atingido.
        """
        state = self.load_state(demand_id)
        if not state:
            return None

        step_config = self._pipeline.get_step(step_id)
        if not step_config or not step_config.on_reject:
            return None

        step_state = state.steps.get(step_id)
        if not step_state:
            return None

        # Registra no histórico de revisão
        step_state.review_cycle += 1
        step_state.review_history.append(
            {
                "cycle": step_state.review_cycle,
                "result": "rejected",
                "feedback": feedback,
                "timestamp": self._now(),
            }
        )

        # Verifica limite de ciclos
        if step_state.review_cycle >= step_config.max_review_cycles:
            state.status = "paused"
            step_state.status = "failed"
            self._save_state(state)
            logger.warning(
                "Max review cycles (%d) atingido para step %s",
                step_config.max_review_cycles,
                step_id,
            )
            return None

        # Volta para o step de on_reject
        target_id = step_config.on_reject
        target_state = state.steps.get(target_id)
        if target_state:
            target_state.status = "running"
            target_state.started_at = self._now()
            # Reseta quality gate para nova tentativa
            target_state.quality_gate_result = ""

        # Reseta step atual para poder re-executar depois
        step_state.status = "pending"
        step_state.quality_gate_result = ""

        state.current_step = target_id
        self._save_state(state)

        logger.info(
            "Reject loop: %s → %s (ciclo %d/%d)",
            step_id,
            target_id,
            step_state.review_cycle,
            step_config.max_review_cycles,
        )
        return target_id

    def skip_step(self, demand_id: str, step_id: str) -> StepConfig | None:
        """Pula um step (override do Squad Lead). Retorna próximo step."""
        state = self.load_state(demand_id)
        if not state:
            return None

        step_state = state.steps.get(step_id)
        if step_state:
            step_state.status = "skipped"
            step_state.completed_at = self._now()

        return self._advance_to_next(state, step_id)

    def rerun_step(self, demand_id: str, step_id: str) -> bool:
        """Re-executa um step (override do Squad Lead)."""
        state = self.load_state(demand_id)
        if not state:
            return False

        step_state = state.steps.get(step_id)
        if not step_state:
            return False

        step_state.status = "running"
        step_state.started_at = self._now()
        step_state.quality_gate_result = ""
        step_state.error = ""
        state.current_step = step_id
        state.status = "running"

        self._save_state(state)
        return True

    def update_agent_status(
        self,
        demand_id: str,
        step_id: str,
        agent_name: str,
        status: str,
    ) -> None:
        """Atualiza status de um agente dentro de um step."""
        state = self.load_state(demand_id)
        if not state:
            return

        step_state = state.steps.get(step_id)
        if step_state:
            step_state.agent_status[agent_name] = status
            self._save_state(state)

    def _format_step_state(
        self,
        step: StepConfig,
        step_state: StepState | None,
    ) -> str:
        """Formata ícone de um step individual para a barra de progresso.

        Retorna representação compacta como '[✅ Spec]' ou '[🔄 Dev (1/3)]'.
        """
        if not step_state:
            return f"[⏳ {step.name}]"

        status_icon = {
            "completed": "✅",
            "running": "🔄",
            "checkpoint": "⏸️",
            "failed": "❌",
            "skipped": "⏭️",
            "pending": "⏳",
        }.get(step_state.status, "⏳")

        suffix = "*" if step.is_checkpoint else ""
        extra = ""
        if step_state.review_cycle > 0:
            step_config = self._pipeline.get_step(step.id)
            max_cycles = step_config.max_review_cycles if step_config else 3
            extra = f" ({step_state.review_cycle}/{max_cycles})"

        return f"[{status_icon} {step.name}{suffix}{extra}]"

    def format_state_for_prompt(self, demand_id: str) -> str:
        """Formata estado do pipeline para injeção no prompt do Squad Lead.

        Gera visualização compacta tipo board:
        [✅ Spec] → [🔄 Dev] → [⏳ Review*] → [⏳ QA]
        """
        state = self.load_state(demand_id)
        if not state:
            return ""

        total_steps = len(self._pipeline.steps)
        current_idx = (
            self._pipeline.get_step_index(state.current_step) + 1 if state.current_step else 0
        )

        lines = [
            f"## Pipeline: {state.pipeline_name} ({state.demand_id}) — step {current_idx}/{total_steps}\n",
        ]

        # Barra visual de progresso
        step_icons = [
            self._format_step_state(step, state.steps.get(step.id)) for step in self._pipeline.steps
        ]
        lines.append(" → ".join(step_icons))

        # Detalhes do step atual
        if state.current_step:
            current_config = self._pipeline.get_step(state.current_step)
            current_state = state.steps.get(state.current_step)
            if current_config and current_state:
                lines.append("")
                agents_str = ", ".join(current_config.all_agents)
                lines.append(f"Step atual: {current_config.name} ({agents_str})")

                # Status individual de agentes
                for agent, astatus in current_state.agent_status.items():
                    lines.append(f"  └ {agent}: {astatus}")

                # Info sobre checkpoint
                if current_config.is_checkpoint:
                    lines.append("  (checkpoint — requer aprovação humana)")

                # Info sobre on_reject
                if current_config.on_reject:
                    lines.append(f"  on_reject: volta para {current_config.on_reject}")

        # Próximo step
        if state.current_step:
            next_step = self._pipeline.next_step(state.current_step)
            if next_step:
                suffix = " (checkpoint)" if next_step.is_checkpoint else ""
                lines.append(f"\nPróximo: {next_step.name}{suffix}")

        lines.append("\n* = checkpoint (requer aprovação humana)")

        return "\n".join(lines)

    def get_active_demands(self) -> list[PipelineState]:
        """Retorna estados de demandas ativas (não concluídas)."""
        active = []
        if not self._state_dir.exists():
            return active

        for demand_dir in self._state_dir.iterdir():
            if not demand_dir.is_dir():
                continue
            state_file = demand_dir / "pipeline-state.json"
            if not state_file.exists():
                continue
            state = self.load_state(demand_dir.name)
            if state and state.status in ("running", "paused"):
                active.append(state)

        return active
