"""Rastreamento de estado do bot por thread.

Gerencia quando o bot deve responder numa thread (ACTIVE),
quando deve ficar quieto (STANDBY) e quando nunca foi chamado (INACTIVE).
"""

import json
import logging
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from ai_squad.orchestrator.atomic_write import write_json_atomic

logger = logging.getLogger("ai-squad.thread-tracker")


class ThreadState(str, Enum):
    """Estado do bot numa thread."""

    INACTIVE = "inactive"  # Bot nunca foi chamado
    ACTIVE = "active"  # Bot lidera a thread
    STANDBY = "standby"  # Humano assumiu, bot recuou


class ThreadAction(str, Enum):
    """Ação que o daemon deve tomar."""

    PROCESS = "process"  # Processar a mensagem
    IGNORE = "ignore"  # Ignorar a mensagem
    HANDOFF = "handoff"  # Transitar para standby e enviar mensagem de handoff


@dataclass
class ThreadInfo:
    """Informações de estado de uma thread."""

    state: str = ThreadState.INACTIVE.value
    activated_at: float = 0.0
    last_bot_message: float = 0.0
    last_human_message: float = 0.0
    human_who_took_over: str = ""


class ThreadTracker:
    """Gerencia estado do bot por thread_id.

    Estados: INACTIVE → ACTIVE → STANDBY → ACTIVE (re-convocado)
    Persistido em state/threads.json via escrita atômica.
    """

    def __init__(
        self,
        state_dir: str | Path,
        standby_timeout: int = 1800,
        inactive_thread_ttl: int = 86400,
        handoff_message: bool = True,
    ) -> None:
        self._state_dir = Path(state_dir)
        self._state_file = self._state_dir / "threads.json"
        self._standby_timeout = standby_timeout
        self._inactive_thread_ttl = inactive_thread_ttl
        self._handoff_message = handoff_message
        self._threads: dict[str, ThreadInfo] = {}

    @property
    def handoff_message_enabled(self) -> bool:
        """Se deve enviar mensagem de handoff ao transitar para standby."""
        return self._handoff_message

    @property
    def standby_timeout(self) -> int:
        """Timeout de standby em segundos."""
        return self._standby_timeout

    def load(self) -> None:
        """Carrega estado de threads do disco e limpa expiradas."""
        if not self._state_file.exists():
            return

        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
            now = time.time()
            for thread_id, data in raw.items():
                info = ThreadInfo(**data)
                # Limpa threads inativas por TTL
                last_activity = max(
                    info.last_bot_message, info.last_human_message, info.activated_at
                )
                if last_activity > 0 and (now - last_activity) > self._inactive_thread_ttl:
                    logger.debug("Thread %s expirada (TTL), removida", thread_id)
                    continue
                self._threads[thread_id] = info
            logger.info("ThreadTracker carregado: %d threads ativas", len(self._threads))
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.warning("Erro ao carregar threads.json: %s", e)

    def save(self) -> None:
        """Persiste estado das threads no disco."""
        data = {tid: asdict(info) for tid, info in self._threads.items()}
        write_json_atomic(self._state_file, data)

    def get_state(self, thread_id: str) -> ThreadState:
        """Retorna estado atual de uma thread."""
        info = self._threads.get(thread_id)
        if not info:
            return ThreadState.INACTIVE
        return ThreadState(info.state)

    def on_message(
        self,
        thread_id: str | None,
        is_bot: bool,
        is_mention: bool,
        user_name: str = "",
    ) -> ThreadAction:
        """Processa mensagem e retorna ação a tomar.

        Args:
            thread_id: ID da thread (None para mensagens sem thread).
            is_bot: Se a mensagem é do próprio bot.
            is_mention: Se a mensagem menciona o bot.
            user_name: Nome do usuário para mensagem de handoff.

        Returns:
            ThreadAction indicando o que fazer.
        """
        # Sem thread_id, não rastreia
        if not thread_id:
            return ThreadAction.PROCESS

        # Ignora mensagens do próprio bot
        if is_bot:
            info = self._threads.get(thread_id)
            if info:
                info.last_bot_message = time.time()
                self.save()
            return ThreadAction.IGNORE

        state = self.get_state(thread_id)
        now = time.time()

        # Menção sempre ativa
        if is_mention:
            info = self._threads.get(thread_id)
            if not info:
                info = ThreadInfo()
                self._threads[thread_id] = info
            info.state = ThreadState.ACTIVE.value
            info.activated_at = now
            info.last_human_message = now
            self.save()
            return ThreadAction.PROCESS

        # INACTIVE — bot nunca foi chamado
        if state == ThreadState.INACTIVE:
            return ThreadAction.IGNORE

        # ACTIVE — humano respondeu sem menção → handoff
        if state == ThreadState.ACTIVE:
            info = self._threads[thread_id]
            info.state = ThreadState.STANDBY.value
            info.last_human_message = now
            info.human_who_took_over = user_name
            self.save()
            return ThreadAction.HANDOFF

        # STANDBY — ignora
        return ThreadAction.IGNORE

    def get_stale_standby_threads(self) -> list[tuple[str, ThreadInfo]]:
        """Retorna threads em standby cujo timeout expirou."""
        now = time.time()
        stale = []
        for thread_id, info in self._threads.items():
            if info.state != ThreadState.STANDBY.value:
                continue
            last_activity = max(info.last_human_message, info.last_bot_message)
            if last_activity > 0 and (now - last_activity) > self._standby_timeout:
                stale.append((thread_id, info))
        return stale

    def reactivate(self, thread_id: str) -> None:
        """Reativa uma thread (ex: após timeout de standby)."""
        info = self._threads.get(thread_id)
        if info:
            info.state = ThreadState.ACTIVE.value
            info.activated_at = time.time()
            self.save()
