"""Persistência de estado de demandas em JSON com escrita atômica."""

import json
from pathlib import Path

from src.orchestrator.atomic_write import write_json_atomic


class StateManager:
    """Gerenciador de estado de demandas com persistência JSON.

    Usa escrita atômica (write-to-temp + fsync + rename) para evitar
    corrupção de dados em caso de crash.

    O estado é armazenado como string simples — o pipeline declarativo
    controla as transições via pipeline-state.json.
    """

    def __init__(self, state_dir: str | Path = "state/") -> None:
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)

    def _state_path(self, demand_id: str) -> Path:
        """Retorna caminho do arquivo de estado de uma demanda."""
        return self._state_dir / f"{demand_id}.json"

    def _load_data(self, path: Path) -> dict:
        """Carrega dados JSON de um arquivo. Retorna {} se não existe ou corrompido."""
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def get_state(self, demand_id: str) -> str:
        """Retorna o estado atual de uma demanda como string."""
        path = self._state_path(demand_id)
        data = self._load_data(path)
        if not data:
            return "idle"
        return data["state"]

    def set_state(
        self,
        demand_id: str,
        state: str,
        checkpoint: dict | None = None,
    ) -> None:
        """Persiste o estado de uma demanda com escrita atômica.

        O checkpoint contém resultados parciais das fases concluídas
        para permitir retomada após crash.
        """
        path = self._state_path(demand_id)
        existing = self._load_data(path)

        data = {
            "demand_id": demand_id,
            "state": state,
            "checkpoint": checkpoint or existing.get("checkpoint", {}),
        }

        # Preserva campos extras (user_id, description, etc.)
        for key in ("user_id", "description"):
            if key in existing:
                data[key] = existing[key]

        write_json_atomic(path, data)

    def save_checkpoint(self, demand_id: str, key: str, value: str) -> None:
        """Salva resultado parcial de uma fase no checkpoint."""
        path = self._state_path(demand_id)
        data = self._load_data(path)
        if not data:
            data = {"demand_id": demand_id, "state": "idle"}

        checkpoint: dict = data.get("checkpoint", {})  # type: ignore[assignment]
        checkpoint[key] = value
        data["checkpoint"] = checkpoint  # type: ignore[index]

        state: str = data.get("state", "idle")  # type: ignore[assignment]
        self.set_state(demand_id, state, checkpoint)

    def get_checkpoint(self, demand_id: str) -> dict:
        """Retorna checkpoint da demanda."""
        data = self._load_data(self._state_path(demand_id))
        return data.get("checkpoint", {})

    def get_all_demands(self) -> dict[str, str]:
        """Retorna estado de todas as demandas persistidas."""
        demands = {}
        for path in self._state_dir.glob("*.json"):
            demand_id = path.stem
            demands[demand_id] = self.get_state(demand_id)
        return demands

    def get_pending_demands(self) -> list[dict]:
        """Retorna demandas com estado não-terminal para retomada."""
        pending = []

        for path in self._state_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                state = data["state"]
                if state not in ("done", "idle"):
                    pending.append(
                        {
                            "demand_id": data["demand_id"],
                            "state": state,
                            "user_id": data.get("user_id", ""),
                            "description": data.get("description", ""),
                            "checkpoint": data.get("checkpoint", {}),
                        }
                    )
            except (json.JSONDecodeError, OSError, KeyError, ValueError):
                continue

        return pending

    def save_user_id(self, demand_id: str, user_id: str) -> None:
        """Salva user_id no estado da demanda para retomada futura."""
        path = self._state_path(demand_id)
        data = self._load_data(path)
        if not data:
            data = {"demand_id": demand_id, "state": "idle"}

        data["user_id"] = user_id
        data.setdefault("demand_id", demand_id)
        data.setdefault("state", "idle")

        write_json_atomic(path, data)

    def delete_state(self, demand_id: str) -> None:
        """Remove estado de uma demanda."""
        path = self._state_path(demand_id)
        if path.exists():
            path.unlink()
