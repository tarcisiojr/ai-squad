"""Mapeamento bidirecional thread_id ↔ demand_id para Forum Topics."""

import json
import logging
from pathlib import Path

from src.orchestrator.atomic_write import write_json_atomic

logger = logging.getLogger("ai-squad.thread-map")


class ThreadDemandMap:
    """Mapeamento persistido entre thread_id (Telegram) e demand_id.

    Permite rotear mensagens de um Forum Topic diretamente
    para a demanda correspondente. Persiste em JSON com escrita atômica.
    """

    def __init__(self, state_dir: str | Path = "state") -> None:
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._state_dir / "thread-demands.json"
        # Mapeamento bidirecional em memória
        self._thread_to_demand: dict[int, str] = {}
        self._demand_to_thread: dict[str, int] = {}
        self.load()

    def load(self) -> None:
        """Carrega mapeamento do disco. Tolerante a falha."""
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Converte chaves de string para int (JSON só suporta string keys)
            self._thread_to_demand = {
                int(k): v for k, v in data.get("thread_to_demand", {}).items()
            }
            self._demand_to_thread = {
                k: int(v) for k, v in data.get("demand_to_thread", {}).items()
            }
            logger.info(
                "Mapeamento thread↔demand carregado: %d entradas",
                len(self._thread_to_demand),
            )
        except (json.JSONDecodeError, OSError, ValueError) as e:
            logger.warning("Erro ao carregar thread-demands.json: %s", e)

    def save(self) -> None:
        """Persiste mapeamento em disco com escrita atômica."""
        data = {
            "thread_to_demand": {str(k): v for k, v in self._thread_to_demand.items()},
            "demand_to_thread": {k: str(v) for k, v in self._demand_to_thread.items()},
        }
        write_json_atomic(self._path, data)

    def add(self, thread_id: int, demand_id: str) -> None:
        """Adiciona mapeamento e persiste."""
        self._thread_to_demand[thread_id] = demand_id
        self._demand_to_thread[demand_id] = thread_id
        self.save()
        logger.info("Mapeamento adicionado: thread=%d ↔ demand=%s", thread_id, demand_id)

    def get_demand(self, thread_id: int) -> str | None:
        """Retorna demand_id associado ao thread_id, ou None."""
        return self._thread_to_demand.get(thread_id)

    def get_thread(self, demand_id: str) -> int | None:
        """Retorna thread_id associado ao demand_id, ou None."""
        return self._demand_to_thread.get(demand_id)
