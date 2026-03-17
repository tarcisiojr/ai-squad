"""Persistência de estado de demandas em JSON com escrita atômica."""

import json
import os
import tempfile
from pathlib import Path

from src.models import DemandState


class StateManager:
    """Gerenciador de estado de demandas com persistência JSON.

    Usa escrita atômica (write-to-temp + rename) para evitar
    corrupção de dados em caso de crash.
    """

    def __init__(self, state_dir: str = "state/") -> None:
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)

    def _state_path(self, demand_id: str) -> Path:
        """Retorna caminho do arquivo de estado de uma demanda."""
        return self._state_dir / f"{demand_id}.json"

    def get_state(self, demand_id: str) -> DemandState:
        """Retorna o estado atual de uma demanda."""
        path = self._state_path(demand_id)
        if not path.exists():
            return DemandState.IDLE

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return DemandState(data["state"])

    def set_state(
        self,
        demand_id: str,
        state: DemandState,
        checkpoint: dict | None = None,
    ) -> None:
        """Persiste o estado de uma demanda com escrita atômica.

        O checkpoint contém resultados parciais das fases concluídas
        para permitir retomada após crash.
        """
        # Carrega dados existentes para preservar checkpoint anterior
        path = self._state_path(demand_id)
        existing = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                existing = {}

        data = {
            "demand_id": demand_id,
            "state": state.value,
            "checkpoint": checkpoint or existing.get("checkpoint", {}),
        }

        # Preserva campos extras (user_id, description, etc.)
        for key in ("user_id", "description"):
            if key in existing:
                data[key] = existing[key]

        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._state_dir), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def save_checkpoint(self, demand_id: str, key: str, value: str) -> None:
        """Salva resultado parcial de uma fase no checkpoint."""
        path = self._state_path(demand_id)
        data = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = {"demand_id": demand_id, "state": "idle"}

        checkpoint = data.get("checkpoint", {})
        checkpoint[key] = value
        data["checkpoint"] = checkpoint

        self.set_state(demand_id, DemandState(data["state"]), checkpoint)

    def get_checkpoint(self, demand_id: str) -> dict:
        """Retorna checkpoint da demanda."""
        path = self._state_path(demand_id)
        if not path.exists():
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("checkpoint", {})
        except (json.JSONDecodeError, OSError):
            return {}

    def get_all_demands(self) -> dict[str, DemandState]:
        """Retorna estado de todas as demandas persistidas."""
        demands = {}
        for path in self._state_dir.glob("*.json"):
            demand_id = path.stem
            demands[demand_id] = self.get_state(demand_id)
        return demands

    def get_pending_demands(self) -> list[dict]:
        """Retorna demandas com estado não-terminal para retomada."""
        terminal_states = {DemandState.DONE, DemandState.IDLE}
        pending = []

        for path in self._state_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                state = DemandState(data["state"])
                if state not in terminal_states:
                    pending.append({
                        "demand_id": data["demand_id"],
                        "state": state,
                        "user_id": data.get("user_id", ""),
                        "description": data.get("description", ""),
                        "checkpoint": data.get("checkpoint", {}),
                    })
            except (json.JSONDecodeError, OSError, KeyError, ValueError):
                continue

        return pending

    def save_user_id(self, demand_id: str, user_id: str) -> None:
        """Salva user_id no estado da demanda para retomada futura."""
        path = self._state_path(demand_id)
        data = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = {"demand_id": demand_id, "state": "idle"}

        data["user_id"] = user_id
        data.setdefault("demand_id", demand_id)
        data.setdefault("state", "idle")

        fd, tmp_path = tempfile.mkstemp(dir=str(self._state_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def delete_state(self, demand_id: str) -> None:
        """Remove estado de uma demanda."""
        path = self._state_path(demand_id)
        if path.exists():
            path.unlink()
