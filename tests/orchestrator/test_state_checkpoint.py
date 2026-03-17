"""Testes para checkpoint e retomada de demandas no StateManager."""

import json

import pytest

from src.orchestrator.state import StateManager


class TestCheckpoint:
    """Testes para checkpoint no StateManager."""

    def test_save_checkpoint(self, tmp_path):
        """Verifica salvamento de checkpoint."""
        mgr = StateManager(state_dir=str(tmp_path))
        mgr.set_state("d-001", "po_working")
        mgr.save_checkpoint("d-001", "plano", "Criar API")

        checkpoint = mgr.get_checkpoint("d-001")
        assert checkpoint["plano"] == "Criar API"

    def test_checkpoint_preservado_na_transicao(self, tmp_path):
        """Verifica que checkpoint é preservado entre transições."""
        mgr = StateManager(state_dir=str(tmp_path))
        mgr.set_state("d-001", "po_working")
        mgr.save_checkpoint("d-001", "plano", "Plano X")

        mgr.set_state("d-001", "awaiting_plan_approval")

        checkpoint = mgr.get_checkpoint("d-001")
        assert checkpoint["plano"] == "Plano X"

    def test_checkpoint_acumula_dados(self, tmp_path):
        """Verifica que múltiplos checkpoints se acumulam."""
        mgr = StateManager(state_dir=str(tmp_path))
        mgr.set_state("d-001", "po_working")
        mgr.save_checkpoint("d-001", "plano", "Plano A")
        mgr.save_checkpoint("d-001", "resultado_dev", "Código B")

        checkpoint = mgr.get_checkpoint("d-001")
        assert checkpoint["plano"] == "Plano A"
        assert checkpoint["resultado_dev"] == "Código B"

    def test_get_checkpoint_inexistente(self, tmp_path):
        """Verifica retorno vazio para demanda inexistente."""
        mgr = StateManager(state_dir=str(tmp_path))
        assert mgr.get_checkpoint("inexistente") == {}


class TestPendingDemands:
    """Testes para detecção de demandas pendentes."""

    def test_get_pending_vazio(self, tmp_path):
        """Verifica lista vazia sem demandas."""
        mgr = StateManager(state_dir=str(tmp_path))
        assert mgr.get_pending_demands() == []

    def test_get_pending_com_demanda_ativa(self, tmp_path):
        """Verifica detecção de demanda ativa."""
        mgr = StateManager(state_dir=str(tmp_path))
        mgr.set_state("d-001", "dev_working")

        pending = mgr.get_pending_demands()
        assert len(pending) == 1
        assert pending[0]["demand_id"] == "d-001"
        assert pending[0]["state"] == "dev_working"

    def test_get_pending_ignora_done(self, tmp_path):
        """Verifica que demandas concluídas são ignoradas."""
        mgr = StateManager(state_dir=str(tmp_path))
        mgr.set_state("d-done", "done")
        mgr.set_state("d-active", "qa_validating")

        pending = mgr.get_pending_demands()
        assert len(pending) == 1
        assert pending[0]["demand_id"] == "d-active"

    def test_get_pending_ignora_idle(self, tmp_path):
        """Verifica que demandas idle são ignoradas."""
        mgr = StateManager(state_dir=str(tmp_path))
        mgr.set_state("d-idle", "idle")

        pending = mgr.get_pending_demands()
        assert len(pending) == 0

    def test_get_pending_com_json_corrompido(self, tmp_path):
        """Verifica que JSON corrompido é ignorado."""
        mgr = StateManager(state_dir=str(tmp_path))
        mgr.set_state("d-ok", "dev_working")

        # Cria JSON corrompido
        (tmp_path / "d-bad.json").write_text("não é json")

        pending = mgr.get_pending_demands()
        assert len(pending) == 1
        assert pending[0]["demand_id"] == "d-ok"

    def test_set_state_com_checkpoint_explicito(self, tmp_path):
        """Verifica set_state com checkpoint explícito."""
        mgr = StateManager(state_dir=str(tmp_path))
        mgr.set_state("d-001", "dev_working", checkpoint={"plano": "X"})

        checkpoint = mgr.get_checkpoint("d-001")
        assert checkpoint["plano"] == "X"
