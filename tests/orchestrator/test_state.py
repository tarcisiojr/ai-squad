"""Testes para persistência de estado."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from ai_squad.orchestrator.state import StateManager


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


class TestDoneAtTimestamp:
    """Testes para registro de done_at ao concluir demanda."""

    @pytest.fixture
    def state_mgr(self, tmp_path):
        return StateManager(state_dir=str(tmp_path / "state"))

    def test_set_state_done_grava_done_at(self, state_mgr, tmp_path):
        """Verifica que set_state("done") grava campo done_at."""
        state_mgr.set_state("d1", "done")
        path = tmp_path / "state" / "d1.json"
        with open(path) as f:
            data = json.load(f)
        assert "done_at" in data
        # Valida formato ISO 8601
        dt = datetime.fromisoformat(data["done_at"])
        assert dt.tzinfo is not None

    def test_set_state_running_nao_grava_done_at(self, state_mgr, tmp_path):
        """Verifica que set_state("running") não grava done_at."""
        state_mgr.set_state("d1", "running")
        path = tmp_path / "state" / "d1.json"
        with open(path) as f:
            data = json.load(f)
        assert "done_at" not in data

    def test_done_at_preservado_em_atualizacoes(self, state_mgr, tmp_path):
        """Verifica que done_at não muda em atualizações subsequentes."""
        state_mgr.set_state("d1", "done")
        path = tmp_path / "state" / "d1.json"
        with open(path) as f:
            original = json.load(f)["done_at"]
        # Atualiza novamente
        state_mgr.set_state("d1", "done")
        with open(path) as f:
            updated = json.load(f)["done_at"]
        assert original == updated


class TestCleanupExpired:
    """Testes para expurgo de demandas concluídas."""

    @pytest.fixture
    def state_mgr(self, tmp_path):
        return StateManager(state_dir=str(tmp_path / "state"))

    def _create_done_demand(self, state_mgr, demand_id: str, days_ago: int) -> None:
        """Cria demanda done com done_at no passado."""
        state_mgr.set_state(demand_id, "done")
        # Sobrescreve done_at para simular passagem de tempo
        path = state_mgr._state_path(demand_id)
        with open(path) as f:
            data = json.load(f)
        past = datetime.now(timezone.utc) - timedelta(days=days_ago)
        data["done_at"] = past.isoformat()
        with open(path, "w") as f:
            json.dump(data, f)

    def test_demanda_expirada_removida(self, state_mgr, tmp_path):
        """Demanda concluída há mais de 1 dia (default) é removida."""
        self._create_done_demand(state_mgr, "old-demand", days_ago=3)
        # Cria subpasta simulando conversation/journal
        subdir = tmp_path / "state" / "old-demand"
        subdir.mkdir()
        (subdir / "conversation.json").write_text("{}")

        removed = state_mgr.cleanup_expired()

        assert removed == 1
        assert not (tmp_path / "state" / "old-demand.json").exists()
        assert not subdir.exists()

    def test_demanda_recente_preservada(self, state_mgr, tmp_path):
        """Demanda concluída há menos de 1 dia (default) é preservada."""
        self._create_done_demand(state_mgr, "recent-demand", days_ago=0)

        removed = state_mgr.cleanup_expired()

        assert removed == 0
        assert (tmp_path / "state" / "recent-demand.json").exists()

    def test_demanda_em_andamento_ignorada(self, state_mgr, tmp_path):
        """Demanda com estado running nunca é removida."""
        state_mgr.set_state("active-demand", "running")

        removed = state_mgr.cleanup_expired()

        assert removed == 0
        assert (tmp_path / "state" / "active-demand.json").exists()

    def test_demanda_legado_sem_done_at_ignorada(self, state_mgr, tmp_path):
        """Demanda done sem done_at (legado) não é removida."""
        # Cria manualmente sem done_at
        path = tmp_path / "state" / "legado.json"
        path.write_text(json.dumps({"demand_id": "legado", "state": "done"}))

        removed = state_mgr.cleanup_expired()

        assert removed == 0
        assert path.exists()

    def test_artefatos_duraveis_preservados(self, state_mgr, tmp_path):
        """lessons.db, graph.db, daily/ e squad-lead-session/ não são afetados."""
        state_dir = tmp_path / "state"
        # Cria artefatos duráveis
        (state_dir / "lessons.db").write_text("data")
        (state_dir / "graph.db").write_text("data")
        (state_dir / "daily").mkdir()
        (state_dir / "daily" / "2026-04-01.txt").write_text("notas")
        (state_dir / "squad-lead-session").mkdir()

        # Cria demanda expirada
        self._create_done_demand(state_mgr, "old", days_ago=10)

        state_mgr.cleanup_expired()

        assert (state_dir / "lessons.db").exists()
        assert (state_dir / "graph.db").exists()
        assert (state_dir / "daily" / "2026-04-01.txt").exists()
        assert (state_dir / "squad-lead-session").exists()

    def test_ttl_customizado(self, state_mgr):
        """TTL configurável funciona corretamente."""
        self._create_done_demand(state_mgr, "d1", days_ago=10)

        # Com TTL de 14 dias, demanda de 10 dias não é removida
        assert state_mgr.cleanup_expired(ttl_days=14) == 0
        # Com TTL de 7 dias, é removida
        assert state_mgr.cleanup_expired(ttl_days=7) == 1

    def test_ttl_invalido_rejeita(self, state_mgr):
        """TTL <= 0 levanta ValueError."""
        with pytest.raises(ValueError):
            state_mgr.cleanup_expired(ttl_days=0)
        with pytest.raises(ValueError):
            state_mgr.cleanup_expired(ttl_days=-1)
