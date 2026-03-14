"""Testes para persistência de estado."""

import json

import pytest

from src.models import DemandState
from src.orchestrator.state import StateManager


class TestStateManager:
    """Testes para StateManager."""

    @pytest.fixture
    def state_mgr(self, tmp_path):
        """Cria StateManager com diretório temporário."""
        return StateManager(state_dir=str(tmp_path / "state"))

    def test_estado_padrao_idle(self, state_mgr):
        """Verifica que demanda inexistente retorna IDLE."""
        state = state_mgr.get_state("demand-nova")
        assert state == DemandState.IDLE

    def test_set_e_get_state(self, state_mgr):
        """Verifica persistência e recuperação de estado."""
        state_mgr.set_state("demand-1", DemandState.PO_WORKING)
        state = state_mgr.get_state("demand-1")
        assert state == DemandState.PO_WORKING

    def test_persistencia_em_arquivo(self, state_mgr, tmp_path):
        """Verifica que estado é persistido em arquivo JSON."""
        state_mgr.set_state("demand-1", DemandState.DEV_WORKING)

        path = tmp_path / "state" / "demand-1.json"
        assert path.exists()

        with open(path) as f:
            data = json.load(f)
        assert data["state"] == "dev_working"
        assert data["demand_id"] == "demand-1"

    def test_recuperacao_apos_nova_instancia(self, tmp_path):
        """Verifica que estado sobrevive a nova instância (simula reinício)."""
        state_dir = str(tmp_path / "state")

        # Primeira instância
        mgr1 = StateManager(state_dir=state_dir)
        mgr1.set_state("demand-1", DemandState.CI_RUNNING)

        # Segunda instância (simula reinício)
        mgr2 = StateManager(state_dir=state_dir)
        state = mgr2.get_state("demand-1")
        assert state == DemandState.CI_RUNNING

    def test_get_all_demands(self, state_mgr):
        """Verifica listagem de todas as demandas."""
        state_mgr.set_state("demand-1", DemandState.PO_WORKING)
        state_mgr.set_state("demand-2", DemandState.DONE)

        demands = state_mgr.get_all_demands()
        assert len(demands) == 2
        assert demands["demand-1"] == DemandState.PO_WORKING
        assert demands["demand-2"] == DemandState.DONE

    def test_delete_state(self, state_mgr):
        """Verifica remoção de estado."""
        state_mgr.set_state("demand-1", DemandState.DONE)
        state_mgr.delete_state("demand-1")

        # Deve retornar IDLE (padrão)
        state = state_mgr.get_state("demand-1")
        assert state == DemandState.IDLE

    def test_delete_state_inexistente(self, state_mgr):
        """Verifica que deletar estado inexistente não falha."""
        state_mgr.delete_state("inexistente")

    def test_escrita_atomica(self, state_mgr, tmp_path):
        """Verifica que escrita atômica não deixa arquivos temporários."""
        state_mgr.set_state("demand-1", DemandState.PO_WORKING)

        state_dir = tmp_path / "state"
        arquivos = list(state_dir.glob("*"))
        # Deve ter apenas o .json, sem .tmp
        assert all(f.suffix == ".json" for f in arquivos)

    def test_multiplas_atualizacoes(self, state_mgr):
        """Verifica que múltiplas atualizações funcionam."""
        state_mgr.set_state("demand-1", DemandState.PO_WORKING)
        state_mgr.set_state("demand-1", DemandState.AWAITING_PLAN_APPROVAL)
        state_mgr.set_state("demand-1", DemandState.DEV_WORKING)

        state = state_mgr.get_state("demand-1")
        assert state == DemandState.DEV_WORKING
