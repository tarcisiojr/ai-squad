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

    def set_state(self, demand_id: str, state: DemandState) -> None:
        """Persiste o estado de uma demanda com escrita atômica."""
        data = {
            "demand_id": demand_id,
            "state": state.value,
        }

        # Escrita atômica: escreve em temp e renomeia
        path = self._state_path(demand_id)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._state_dir), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, path)
        except Exception:
            # Remove arquivo temporário em caso de erro
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def get_all_demands(self) -> dict[str, DemandState]:
        """Retorna estado de todas as demandas persistidas."""
        demands = {}
        for path in self._state_dir.glob("*.json"):
            demand_id = path.stem
            demands[demand_id] = self.get_state(demand_id)
        return demands

    def delete_state(self, demand_id: str) -> None:
        """Remove estado de uma demanda."""
        path = self._state_path(demand_id)
        if path.exists():
            path.unlink()
