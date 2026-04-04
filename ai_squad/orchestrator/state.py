"""Persistência de estado de demandas em JSON com escrita atômica."""

import json
import logging
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_squad.orchestrator.atomic_write import write_json_atomic

logger = logging.getLogger("ai-squad.state")

# Padrão seguro para demand_id: apenas alfanuméricos, hífens e underscores
_SAFE_ID = re.compile(r"^[a-zA-Z0-9_\-]+$")


@dataclass
class DemandState:
    """Representação tipada do estado persistido de uma demanda.

    Encapsula os campos do JSON de estado, oferecendo conversão
    bidirecional (dict <-> dataclass) para compatibilidade retroativa.
    """

    demand_id: str
    state: str = "idle"
    checkpoint: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())
    user_id: str = ""
    description: str = ""
    done_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário, omitindo campos vazios/None opcionais."""
        data = asdict(self)
        # Remove campos opcionais vazios para manter compatibilidade com JSON existente
        if not data.get("user_id"):
            data.pop("user_id", None)
        if not data.get("description"):
            data.pop("description", None)
        if data.get("done_at") is None:
            data.pop("done_at", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DemandState":
        """Cria instância a partir de dicionário, ignorando chaves desconhecidas."""
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


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

    @property
    def state_dir(self) -> Path:
        """Caminho público do diretório de estado."""
        return self._state_dir

    def _validate_id(self, demand_id: str) -> None:
        """Valida que demand_id não contém caracteres perigosos (path traversal)."""
        if not _SAFE_ID.match(demand_id):
            raise ValueError(f"demand_id inválido: {demand_id!r}")

    def _state_path(self, demand_id: str) -> Path:
        """Retorna caminho do arquivo de estado de uma demanda."""
        self._validate_id(demand_id)
        return self._state_dir / f"{demand_id}.json"

    def _load_data(self, path: Path) -> dict[str, Any]:
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
        checkpoint: dict[str, Any] | None = None,
    ) -> None:
        """Persiste o estado de uma demanda com escrita atômica.

        O checkpoint contém resultados parciais das fases concluídas
        para permitir retomada após crash.
        """
        path = self._state_path(demand_id)
        existing = self._load_data(path)

        data: dict[str, Any] = {
            "demand_id": demand_id,
            "state": state,
            "checkpoint": checkpoint or existing.get("checkpoint", {}),
        }

        # Registra timestamp de conclusão ao entrar em "done"
        if state == "done" and "done_at" not in existing:
            data["done_at"] = datetime.now(timezone.utc).isoformat()
        elif "done_at" in existing:
            data["done_at"] = existing["done_at"]

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

        checkpoint: dict[str, Any] = {}
        if isinstance(data.get("checkpoint"), dict):
            checkpoint = data["checkpoint"]  # type: ignore[assignment]
        checkpoint[key] = value

        state: str = str(data.get("state", "idle"))
        self.set_state(demand_id, state, checkpoint)

    def get_checkpoint(self, demand_id: str) -> dict[str, Any]:
        """Retorna checkpoint da demanda."""
        data = self._load_data(self._state_path(demand_id))
        return data.get("checkpoint", {})

    def get_all_demands(self) -> dict[str, str]:
        """Retorna estado de todas as demandas persistidas."""
        demands: dict[str, str] = {}
        for path in self._state_dir.glob("*.json"):
            demand_id = path.stem
            demands[demand_id] = self.get_state(demand_id)
        return demands

    def get_pending_demands(self) -> list[dict[str, Any]]:
        """Retorna demandas com estado não-terminal para retomada."""
        pending: list[dict[str, Any]] = []

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

    def cleanup_expired(self, ttl_days: int = 1) -> int:
        """Remove demandas concluídas há mais de ttl_days dias.

        Remove o arquivo .json de estado e a subpasta associada
        (conversation, journal, pipeline-state). Preserva artefatos
        duráveis (lessons.db, graph.db, daily/, etc.).

        Retorna quantidade de demandas removidas.
        """
        if ttl_days <= 0:
            raise ValueError(f"ttl_days deve ser positivo, recebeu: {ttl_days}")

        now = datetime.now(timezone.utc)
        removed = 0

        for path in list(self._state_dir.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if data.get("state") != "done":
                    continue

                done_at_str = data.get("done_at")
                if not done_at_str:
                    logger.warning(
                        "Demanda %s em estado done sem done_at (legado), ignorando",
                        path.stem,
                    )
                    continue

                done_at = datetime.fromisoformat(done_at_str)
                age_days = (now - done_at).days
                if age_days < ttl_days:
                    continue

                # Remove arquivo de estado
                demand_id = path.stem
                path.unlink()

                # Remove subpasta associada (conversation, journal, pipeline-state)
                subdir = self._state_dir / demand_id
                if subdir.is_dir():
                    shutil.rmtree(subdir)

                logger.info("Demanda %s removida (concluída há %d dias)", demand_id, age_days)
                removed += 1

            except (json.JSONDecodeError, OSError, KeyError, ValueError) as e:
                logger.warning("Erro ao processar %s no cleanup: %s", path.name, e)
                continue

        if removed:
            logger.info("Cleanup: %d demanda(s) expirada(s) removida(s)", removed)

        return removed
