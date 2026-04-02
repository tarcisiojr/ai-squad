"""Testes para persistência de estado."""

import json

import pytest

from src.orchestrator.state import StateManager


class TestStateManager:
    """Testes para StateManager."""

    @pytest.fixture
    def state_mgr(self, tmp_path):
        """Cria StateManager com diretório temporário."""
        return StateManager(state_dir=str(tmp_path / "state"))

    def test_estado_padrao_idle(self, state_mgr):
        """Verifica que demanda inexistente retorna 'idle'."""
        state = state_mgr.get_state("demand-nova")
        assert state == "idle"

    def test_set_e_get_state(self, state_mgr):
        """Verifica persistência e recuperação de estado."""
        state_mgr.set_state("demand-1", "po_working")
        state = state_mgr.get_state("demand-1")
        assert state == "po_working"

    def test_persistencia_em_arquivo(self, state_mgr, tmp_path):
        """Verifica que estado é persistido em arquivo JSON."""
        state_mgr.set_state("demand-1", "dev_working")

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
        mgr1.set_state("demand-1", "ci_running")

        # Segunda instância (simula reinício)
        mgr2 = StateManager(state_dir=state_dir)
        state = mgr2.get_state("demand-1")
        assert state == "ci_running"

    def test_get_all_demands(self, state_mgr):
        """Verifica listagem de todas as demandas."""
        state_mgr.set_state("demand-1", "po_working")
        state_mgr.set_state("demand-2", "done")

        demands = state_mgr.get_all_demands()
        assert len(demands) == 2
        assert demands["demand-1"] == "po_working"
        assert demands["demand-2"] == "done"

    def test_delete_state(self, state_mgr):
        """Verifica remoção de estado."""
        state_mgr.set_state("demand-1", "done")
        state_mgr.delete_state("demand-1")

        # Deve retornar "idle" (padrão)
        state = state_mgr.get_state("demand-1")
        assert state == "idle"

    def test_delete_state_inexistente(self, state_mgr):
        """Verifica que deletar estado inexistente não falha."""
        state_mgr.delete_state("inexistente")

    def test_escrita_atomica(self, state_mgr, tmp_path):
        """Verifica que escrita atômica não deixa arquivos temporários."""
        state_mgr.set_state("demand-1", "po_working")

        state_dir = tmp_path / "state"
        arquivos = list(state_dir.glob("*"))
        # Deve ter apenas o .json, sem .tmp
        assert all(f.suffix == ".json" for f in arquivos)

    def test_multiplas_atualizacoes(self, state_mgr):
        """Verifica que múltiplas atualizações funcionam."""
        state_mgr.set_state("demand-1", "po_working")
        state_mgr.set_state("demand-1", "awaiting_plan_approval")
        state_mgr.set_state("demand-1", "dev_working")

        state = state_mgr.get_state("demand-1")
        assert state == "dev_working"

    @pytest.mark.parametrize(
        "demand_id",
        ["my-demand-123", "test_id", "ABC", "simples", "a1-b2_c3"],
    )
    def test_demand_id_valido_aceito(self, state_mgr, demand_id):
        """Verifica que demand_ids válidos são aceitos sem erro."""
        state_mgr.set_state(demand_id, "idle")
        assert state_mgr.get_state(demand_id) == "idle"

    @pytest.mark.parametrize(
        "demand_id",
        ["../../etc/passwd", "../hack", "foo/bar", "a b", "id;rm", ""],
    )
    def test_demand_id_path_traversal_rejeita(self, state_mgr, demand_id):
        """Verifica que tentativas de path traversal levantam ValueError."""
        with pytest.raises(ValueError, match="demand_id inválido"):
            state_mgr.set_state(demand_id, "idle")

    @pytest.mark.parametrize(
        "demand_id",
        ["../../etc/passwd", "../hack", "foo/bar"],
    )
    def test_get_state_path_traversal_rejeita(self, state_mgr, demand_id):
        """Verifica que get_state também rejeita ids maliciosos."""
        with pytest.raises(ValueError, match="demand_id inválido"):
            state_mgr.get_state(demand_id)
