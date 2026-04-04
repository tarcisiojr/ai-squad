"""Persistência de decisões e contexto do Squad Lead por demanda."""

import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_squad.orchestrator.atomic_write import write_json_atomic

logger = logging.getLogger("ai-squad.journal")


@dataclass
class JournalEntry:
    """Representação tipada de uma entrada do journal de demanda.

    Encapsula os campos persistidos no JSON do journal,
    oferecendo conversão bidirecional (dict <-> dataclass)
    para compatibilidade retroativa.
    """

    demand_id: str
    demand_text: str = ""
    created_at: str = ""
    updated_at: str = ""
    current_phase: str = "idle"
    decisions: list[dict[str, str]] = field(default_factory=lambda: list[dict[str, str]]())
    next_expected: dict[str, str] | None = None
    context_notes: list[str] = field(default_factory=lambda: list[str]())
    auto_retries: int = 0
    # Campos adicionados dinamicamente por get_stalled / get_pending_approvals
    stalled_seconds: float | None = None
    waiting_seconds: float | None = None
    # Campo de conclusão (presente em estados "done")
    done_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário, omitindo campos None opcionais."""
        data = asdict(self)
        # Remove campos auxiliares que são None para manter compatibilidade
        for key in ("stalled_seconds", "waiting_seconds", "done_at"):
            if data.get(key) is None:
                data.pop(key, None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JournalEntry":
        """Cria instância a partir de dicionário, ignorando chaves desconhecidas."""
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


class JournalStore:
    """Persiste decisões e contexto do Squad Lead por demanda.

    Cada demanda tem um journal em state/{demand_id}/squad-lead-journal.json
    que registra decisões tomadas, próxima ação esperada e notas de contexto.
    Escrita atômica via temp + rename para prevenir corrupção.
    """

    def __init__(self, state_dir: str | Path = "state") -> None:
        self._state_dir = Path(state_dir)

    def _journal_path(self, demand_id: str) -> Path:
        """Caminho do journal para uma demanda."""
        return self._state_dir / demand_id / "squad-lead-journal.json"

    def _write_atomic(self, path: Path, data: dict[str, Any]) -> None:
        """Escrita atômica via utilitário compartilhado."""
        write_json_atomic(path, data)

    def _now(self) -> str:
        """Timestamp ISO-8601 UTC."""
        return datetime.now(timezone.utc).isoformat()

    def create(self, demand_id: str, demand_text: str) -> dict[str, Any]:
        """Cria journal para nova demanda."""
        journal: dict[str, Any] = {
            "demand_id": demand_id,
            "demand_text": demand_text,
            "created_at": self._now(),
            "updated_at": self._now(),
            "current_phase": "idle",
            "decisions": [],
            "next_expected": None,
            "context_notes": [],
            "auto_retries": 0,
        }
        self._write_atomic(self._journal_path(demand_id), journal)
        logger.info("Journal criado: %s", demand_id)
        return journal

    def read(self, demand_id: str) -> dict[str, Any] | None:
        """Lê journal de uma demanda. Retorna None se não existe."""
        path = self._journal_path(demand_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Erro ao ler journal %s: %s", demand_id, e)
            return None

    def _update(
        self, demand_id: str, updater: Callable[[dict[str, Any]], None]
    ) -> dict[str, Any] | None:
        """Lê, aplica updater, salva. Retorna journal atualizado."""
        journal = self.read(demand_id)
        if journal is None:
            return None
        updater(journal)
        journal["updated_at"] = self._now()
        self._write_atomic(self._journal_path(demand_id), journal)
        return journal

    def add_decision(self, demand_id: str, action: str, detail: str) -> dict[str, Any] | None:
        """Registra decisão tomada pelo Squad Lead."""

        def updater(j: dict[str, Any]) -> None:
            j["decisions"].append(
                {
                    "timestamp": self._now(),
                    "action": action,
                    "detail": detail,
                }
            )

        result = self._update(demand_id, updater)
        if result:
            logger.info("Decisão registrada [%s]: %s", demand_id, action)
        return result

    def set_next_expected(
        self,
        demand_id: str,
        action: str,
        agent: str,
        description: str,
    ) -> dict[str, Any] | None:
        """Define próxima ação esperada."""

        def updater(j: dict[str, Any]) -> None:
            j["next_expected"] = {
                "action": action,
                "agent": agent,
                "description": description,
            }

        return self._update(demand_id, updater)

    def set_phase(self, demand_id: str, phase: str) -> dict[str, Any] | None:
        """Atualiza fase atual da demanda.

        Ao marcar como 'done', limpa next_expected para evitar que
        a demanda apareça como ativa em retomadas futuras.
        """

        def updater(j: dict[str, Any]) -> None:
            j["current_phase"] = phase
            if phase == "done":
                j["next_expected"] = None

        return self._update(demand_id, updater)

    def add_context_note(self, demand_id: str, note: str) -> dict[str, Any] | None:
        """Adiciona nota de contexto relevante."""

        def updater(j: dict[str, Any]) -> None:
            j["context_notes"].append(note)

        return self._update(demand_id, updater)

    def increment_retries(self, demand_id: str) -> dict[str, Any] | None:
        """Incrementa contador de retomadas automáticas."""

        def updater(j: dict[str, Any]) -> None:
            j["auto_retries"] = j.get("auto_retries", 0) + 1

        return self._update(demand_id, updater)

    def get_active_journals(self) -> list[dict[str, Any]]:
        """Retorna journals de demandas ativas.

        Considera ativo se:
        - current_phase não é 'done' nem 'idle'
        - OU phase='idle' com next_expected recente (< 1h) — indica
          trabalho em andamento que pode ter sido interrompido
        Demandas idle com next_expected stale (> 1h) são ignoradas
        para evitar re-despacho após restart do daemon.
        """
        active: list[dict[str, Any]] = []
        if not self._state_dir.exists():
            return active

        now = datetime.now(timezone.utc)

        for demand_dir in self._state_dir.iterdir():
            if not demand_dir.is_dir():
                continue
            journal_path = demand_dir / "squad-lead-journal.json"
            if not journal_path.exists():
                continue
            try:
                with open(journal_path, "r", encoding="utf-8") as f:
                    journal = json.load(f)
                phase = journal.get("current_phase", "idle")

                # Demandas concluídas nunca são ativas
                if phase == "done":
                    continue

                # Demandas em andamento (não idle, não done) são sempre ativas
                if phase != "idle":
                    active.append(journal)
                    continue

                # Phase idle: só é ativa se foi atualizada recentemente (< 1h)
                # Isso evita re-despacho de demandas stale após restart
                updated_at_str = journal.get("updated_at", "")
                if updated_at_str:
                    try:
                        updated_at = datetime.fromisoformat(updated_at_str)
                        age_hours = (now - updated_at).total_seconds() / 3600
                        if age_hours > 1:
                            continue
                    except (ValueError, TypeError):
                        pass

                has_next = bool(journal.get("next_expected"))
                has_decisions = len(journal.get("decisions", [])) > 0
                if has_next or has_decisions:
                    active.append(journal)

            except (json.JSONDecodeError, OSError):
                continue

        return active

    def get_active_summaries(self) -> str:
        """Retorna resumo formatado de journals ativos para injeção no prompt."""
        active = self.get_active_journals()
        if not active:
            return "Nenhuma demanda ativa."

        lines: list[str] = []
        for j in active:
            demand_id = j.get("demand_id", "?")
            demand_text = j.get("demand_text", "?")
            phase = j.get("current_phase", "?")
            next_exp = j.get("next_expected")
            updated = j.get("updated_at", "")

            line = f'- **{demand_id}**: "{demand_text}" — fase: {phase}'
            if next_exp:
                line += f" — próximo: {next_exp.get('description', '?')}"
            if updated:
                line += f" (atualizado: {updated})"
            lines.append(line)

        return "\n".join(lines)

    def get_stalled(self, stall_timeout: int = 1800) -> list[dict[str, Any]]:
        """Retorna demandas paradas (sem atualização > timeout segundos).

        Demandas em awaiting_plan_approval ou awaiting_pr_approval
        NÃO são consideradas paradas — estão aguardando o usuário.
        """
        approval_states = {"awaiting_plan_approval", "awaiting_pr_approval"}
        stalled: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for journal in self.get_active_journals():
            phase = journal.get("current_phase", "idle")
            if phase in approval_states:
                continue

            updated_str = journal.get("updated_at", "")
            if not updated_str:
                continue

            try:
                updated_at = datetime.fromisoformat(updated_str)
                elapsed = (now - updated_at).total_seconds()
                if elapsed > stall_timeout:
                    journal["stalled_seconds"] = elapsed
                    stalled.append(journal)
            except (ValueError, TypeError):
                continue

        return stalled

    def get_pending_approvals(self, reminder_timeout: int = 3600) -> list[dict[str, Any]]:
        """Retorna demandas aguardando aprovação há mais de reminder_timeout."""
        approval_states = {"awaiting_plan_approval", "awaiting_pr_approval"}
        pending: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for journal in self.get_active_journals():
            phase = journal.get("current_phase", "idle")
            if phase not in approval_states:
                continue

            updated_str = journal.get("updated_at", "")
            if not updated_str:
                continue

            try:
                updated_at = datetime.fromisoformat(updated_str)
                elapsed = (now - updated_at).total_seconds()
                if elapsed > reminder_timeout:
                    journal["waiting_seconds"] = elapsed
                    pending.append(journal)
            except (ValueError, TypeError):
                continue

        return pending
