"""Notas diárias — resumo do que foi feito por dia.

Inspirado no PicoClaw: salva resumos diários em state/daily/YYYY-MM-DD.md
e injeta os últimos 3 dias no prompt do Squad Lead para continuidade
entre sessões.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ai_squad.orchestrator.atomic_write import write_text_atomic

logger = logging.getLogger("ai-squad.daily-notes")


class DailyNotes:
    """Persiste e recupera notas diárias para continuidade entre sessões."""

    # Quantos dias recentes injetar no prompt
    DAYS_TO_INJECT = 3

    def __init__(self, state_dir: str | Path = "state") -> None:
        self._daily_dir = Path(state_dir) / "daily"
        self._daily_dir.mkdir(parents=True, exist_ok=True)

    def _note_path(self, day: date) -> Path:
        """Retorna caminho do arquivo de nota para um dia."""
        return self._daily_dir / f"{day.isoformat()}.md"

    def add_entry(self, entry: str, day: date | None = None) -> None:
        """Adiciona uma entrada à nota do dia.

        Cada entrada é um item com timestamp, acumulado no arquivo do dia.
        """
        if day is None:
            day = datetime.now(timezone.utc).date()

        path = self._note_path(day)
        timestamp = datetime.now(timezone.utc).strftime("%H:%M")

        new_line = f"- [{timestamp}] {entry}\n"

        # Acumula no arquivo existente
        existing = ""
        if path.exists():
            try:
                existing = path.read_text(encoding="utf-8")
            except OSError:
                pass

        if not existing:
            existing = f"# {day.isoformat()}\n\n"

        content = existing + new_line
        self._write_atomic(path, content)

    def add_demand_completed(
        self,
        demand_id: str,
        demand_text: str,
        day: date | None = None,
    ) -> None:
        """Registra conclusão de demanda na nota do dia."""
        self.add_entry(
            f"Demanda concluída: {demand_id} — {demand_text[:100]}",
            day=day,
        )

    def add_agent_event(
        self,
        agent_name: str,
        event: str,
        day: date | None = None,
    ) -> None:
        """Registra evento de agente na nota do dia."""
        self.add_entry(f"{agent_name}: {event}", day=day)

    def load_day(self, day: date) -> str:
        """Carrega nota de um dia específico."""
        path = self._note_path(day)
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def load_recent(self, days: int | None = None) -> str:
        """Carrega notas dos últimos N dias.

        Retorna texto formatado com notas recentes para injeção no prompt.
        """
        if days is None:
            days = self.DAYS_TO_INJECT

        today = datetime.now(timezone.utc).date()
        partes: list[str] = []

        for i in range(days):
            day = today - timedelta(days=i)
            content = self.load_day(day)
            if content:
                partes.append(content)

        if not partes:
            return ""

        return "## Notas recentes (últimos dias)\n\n" + "\n\n".join(partes)

    def _write_atomic(self, path: Path, content: str) -> None:
        """Escrita atômica via utilitário compartilhado."""
        write_text_atomic(path, content)
