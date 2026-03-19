"""Testes para o ThreadTracker."""

import json
import time

import pytest

from src.orchestrator.thread_tracker import (
    ThreadAction,
    ThreadInfo,
    ThreadState,
    ThreadTracker,
)


class TestThreadTrackerTransitions:
    """Testes de transição de estado por thread."""

    def test_thread_inativa_ignora(self, tmp_path) -> None:
        """Thread sem menção prévia é ignorada."""
        tracker = ThreadTracker(state_dir=tmp_path)
        action = tracker.on_message("thread-1", is_bot=False, is_mention=False)
        assert action == ThreadAction.IGNORE

    def test_mencao_ativa_thread(self, tmp_path) -> None:
        """Menção ativa a thread."""
        tracker = ThreadTracker(state_dir=tmp_path)
        action = tracker.on_message("thread-1", is_bot=False, is_mention=True)
        assert action == ThreadAction.PROCESS
        assert tracker.get_state("thread-1") == ThreadState.ACTIVE

    def test_humano_sem_mencao_faz_handoff(self, tmp_path) -> None:
        """Humano responde sem menção → handoff."""
        tracker = ThreadTracker(state_dir=tmp_path)
        # Primeiro ativa
        tracker.on_message("thread-1", is_bot=False, is_mention=True)
        # Humano responde sem menção
        action = tracker.on_message("thread-1", is_bot=False, is_mention=False, user_name="João")
        assert action == ThreadAction.HANDOFF
        assert tracker.get_state("thread-1") == ThreadState.STANDBY

    def test_standby_ignora_mensagem(self, tmp_path) -> None:
        """Thread em standby ignora mensagens sem menção."""
        tracker = ThreadTracker(state_dir=tmp_path)
        tracker.on_message("thread-1", is_bot=False, is_mention=True)
        tracker.on_message("thread-1", is_bot=False, is_mention=False)
        # Outra mensagem sem menção
        action = tracker.on_message("thread-1", is_bot=False, is_mention=False)
        assert action == ThreadAction.IGNORE

    def test_reconvocacao_reativa(self, tmp_path) -> None:
        """Menção em standby reativa a thread."""
        tracker = ThreadTracker(state_dir=tmp_path)
        tracker.on_message("thread-1", is_bot=False, is_mention=True)
        tracker.on_message("thread-1", is_bot=False, is_mention=False)  # standby
        assert tracker.get_state("thread-1") == ThreadState.STANDBY
        # Re-convocação
        action = tracker.on_message("thread-1", is_bot=False, is_mention=True)
        assert action == ThreadAction.PROCESS
        assert tracker.get_state("thread-1") == ThreadState.ACTIVE

    def test_mensagem_bot_ignorada(self, tmp_path) -> None:
        """Mensagens do próprio bot são ignoradas."""
        tracker = ThreadTracker(state_dir=tmp_path)
        tracker.on_message("thread-1", is_bot=False, is_mention=True)
        action = tracker.on_message("thread-1", is_bot=True, is_mention=False)
        assert action == ThreadAction.IGNORE
        # Estado não muda
        assert tracker.get_state("thread-1") == ThreadState.ACTIVE

    def test_sem_thread_id_processa(self, tmp_path) -> None:
        """Mensagem sem thread_id sempre é processada."""
        tracker = ThreadTracker(state_dir=tmp_path)
        action = tracker.on_message(None, is_bot=False, is_mention=False)
        assert action == ThreadAction.PROCESS


class TestThreadTrackerPersistence:
    """Testes de persistência (save/load)."""

    def test_save_e_load(self, tmp_path) -> None:
        """Estado salvo é restaurado corretamente."""
        tracker = ThreadTracker(state_dir=tmp_path)
        tracker.on_message("thread-1", is_bot=False, is_mention=True)
        tracker.on_message("thread-2", is_bot=False, is_mention=True)

        # Novo tracker carrega do disco
        tracker2 = ThreadTracker(state_dir=tmp_path)
        tracker2.load()
        assert tracker2.get_state("thread-1") == ThreadState.ACTIVE
        assert tracker2.get_state("thread-2") == ThreadState.ACTIVE

    def test_load_sem_arquivo(self, tmp_path) -> None:
        """Load sem arquivo não falha."""
        tracker = ThreadTracker(state_dir=tmp_path)
        tracker.load()  # Não deve levantar exceção
        assert tracker.get_state("thread-1") == ThreadState.INACTIVE


class TestThreadTrackerTTL:
    """Testes de limpeza por TTL."""

    def test_limpa_threads_expiradas(self, tmp_path) -> None:
        """Threads com última atividade > TTL são removidas no load."""
        # Cria estado com thread antiga
        state_file = tmp_path / "threads.json"
        old_time = time.time() - 100000  # Bem mais que 86400
        data = {
            "thread-old": {
                "state": "active",
                "activated_at": old_time,
                "last_bot_message": old_time,
                "last_human_message": 0.0,
                "human_who_took_over": "",
            },
            "thread-new": {
                "state": "active",
                "activated_at": time.time(),
                "last_bot_message": time.time(),
                "last_human_message": 0.0,
                "human_who_took_over": "",
            },
        }
        state_file.write_text(json.dumps(data))

        tracker = ThreadTracker(state_dir=tmp_path, inactive_thread_ttl=86400)
        tracker.load()

        assert tracker.get_state("thread-old") == ThreadState.INACTIVE  # Removida
        assert tracker.get_state("thread-new") == ThreadState.ACTIVE  # Mantida


class TestThreadTrackerStandbyTimeout:
    """Testes de timeout de standby."""

    def test_detecta_threads_stale(self, tmp_path) -> None:
        """Detecta threads em standby cujo timeout expirou."""
        tracker = ThreadTracker(state_dir=tmp_path, standby_timeout=10)
        # Ativa e faz handoff
        tracker.on_message("thread-1", is_bot=False, is_mention=True)
        tracker.on_message("thread-1", is_bot=False, is_mention=False)

        # Simula passagem de tempo
        info = tracker._threads["thread-1"]
        info.last_human_message = time.time() - 20  # 20s atrás (> 10s timeout)

        stale = tracker.get_stale_standby_threads()
        assert len(stale) == 1
        assert stale[0][0] == "thread-1"

    def test_reactivate(self, tmp_path) -> None:
        """Reativação muda estado para ACTIVE."""
        tracker = ThreadTracker(state_dir=tmp_path)
        tracker.on_message("thread-1", is_bot=False, is_mention=True)
        tracker.on_message("thread-1", is_bot=False, is_mention=False)
        assert tracker.get_state("thread-1") == ThreadState.STANDBY

        tracker.reactivate("thread-1")
        assert tracker.get_state("thread-1") == ThreadState.ACTIVE
