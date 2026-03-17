"""Persistência de decisões e contexto do Squad Lead por demanda."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.orchestrator.atomic_write import write_json_atomic

logger = logging.getLogger("ai-dev-team.journal")


class JournalStore:
    """Persiste decisões e contexto do Squad Lead por demanda.

    Cada demanda tem um journal em state/{demand_id}/squad-lead-journal.json
    que registra decisões tomadas, próxima ação esperada e notas de contexto.
    Escrita atômica via temp + rename para prevenir corrupção.
    """

    def __init__(self, state_dir: str = "state") -> None:
        self._state_dir = Path(state_dir)

    def _journal_path(self, demand_id: str) -> Path:
        """Caminho do journal para uma demanda."""
        return self._state_dir / demand_id / "squad-lead-journal.json"

    def _write_atomic(self, path: Path, data: dict) -> None:
        """Escrita atômica via utilitário compartilhado."""
        write_json_atomic(path, data)

    def _now(self) -> str:
        """Timestamp ISO-8601 UTC."""
        return datetime.now(timezone.utc).isoformat()

    def create(self, demand_id: str, demand_text: str) -> dict:
        """Cria journal para nova demanda."""
        journal = {
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

    def read(self, demand_id: str) -> dict | None:
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

    def _update(self, demand_id: str, updater: callable) -> dict | None:
        """Lê, aplica updater, salva. Retorna journal atualizado."""
        journal = self.read(demand_id)
        if journal is None:
            return None
        updater(journal)
        journal["updated_at"] = self._now()
        self._write_atomic(self._journal_path(demand_id), journal)
        return journal

    def add_decision(self, demand_id: str, action: str, detail: str) -> dict | None:
        """Registra decisão tomada pelo Squad Lead."""
        def updater(j: dict) -> None:
            j["decisions"].append({
                "timestamp": self._now(),
                "action": action,
                "detail": detail,
            })
        result = self._update(demand_id, updater)
        if result:
            logger.info("Decisão registrada [%s]: %s", demand_id, action)
        return result

    def set_next_expected(
        self, demand_id: str, action: str, agent: str, description: str,
    ) -> dict | None:
        """Define próxima ação esperada."""
        def updater(j: dict) -> None:
            j["next_expected"] = {
                "action": action,
                "agent": agent,
                "description": description,
            }
        return self._update(demand_id, updater)

    def set_phase(self, demand_id: str, phase: str) -> dict | None:
        """Atualiza fase atual da demanda."""
        def updater(j: dict) -> None:
            j["current_phase"] = phase
        return self._update(demand_id, updater)

    def add_context_note(self, demand_id: str, note: str) -> dict | None:
        """Adiciona nota de contexto relevante."""
        def updater(j: dict) -> None:
            j["context_notes"].append(note)
        return self._update(demand_id, updater)

    def increment_retries(self, demand_id: str) -> dict | None:
        """Incrementa contador de retomadas automáticas."""
        def updater(j: dict) -> None:
            j["auto_retries"] = j.get("auto_retries", 0) + 1
        return self._update(demand_id, updater)

    def get_active_journals(self) -> list[dict]:
        """Retorna journals de demandas ativas.

        Considera ativo se:
        - current_phase nao e 'done'
        - OU tem next_expected definido (trabalho pendente mesmo com phase idle)
        """
        active = []
        if not self._state_dir.exists():
            return active

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
                has_next = bool(journal.get("next_expected"))
                has_decisions = len(journal.get("decisions", [])) > 0

                # Ativo se nao concluido E tem trabalho pendente ou decisoes
                if phase != "done" and (phase != "idle" or has_next or has_decisions):
                    active.append(journal)
            except (json.JSONDecodeError, OSError):
                continue

        return active

    def get_active_summaries(self) -> str:
        """Retorna resumo formatado de journals ativos para injeção no prompt."""
        active = self.get_active_journals()
        if not active:
            return "Nenhuma demanda ativa."

        lines = []
        for j in active:
            demand_id = j.get("demand_id", "?")
            demand_text = j.get("demand_text", "?")
            phase = j.get("current_phase", "?")
            next_exp = j.get("next_expected")
            updated = j.get("updated_at", "")

            line = f"- **{demand_id}**: \"{demand_text}\" — fase: {phase}"
            if next_exp:
                line += f" — próximo: {next_exp.get('description', '?')}"
            if updated:
                line += f" (atualizado: {updated})"
            lines.append(line)

        return "\n".join(lines)

    def get_stalled(self, stall_timeout: int = 1800) -> list[dict]:
        """Retorna demandas paradas (sem atualização > timeout segundos).

        Demandas em awaiting_plan_approval ou awaiting_pr_approval
        NÃO são consideradas paradas — estão aguardando o usuário.
        """
        approval_states = {"awaiting_plan_approval", "awaiting_pr_approval"}
        stalled = []
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

    def get_pending_approvals(self, reminder_timeout: int = 3600) -> list[dict]:
        """Retorna demandas aguardando aprovação há mais de reminder_timeout."""
        approval_states = {"awaiting_plan_approval", "awaiting_pr_approval"}
        pending = []
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
