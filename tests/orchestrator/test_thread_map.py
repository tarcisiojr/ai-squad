"""Testes para ThreadDemandMap — mapeamento thread_id ↔ demand_id."""

import json

import pytest

from ai_squad.orchestrator.thread_map import ThreadDemandMap


class TestThreadDemandMap:
    """Testes unitários para ThreadDemandMap."""

    @pytest.fixture
    def state_dir(self, tmp_path):
        """Diretório temporário para state."""
        return tmp_path / "state"

    @pytest.fixture
    def thread_map(self, state_dir):
        """Cria instância de ThreadDemandMap."""
        return ThreadDemandMap(state_dir=state_dir)

    def test_add_e_get_demand(self, thread_map):
        """Verifica que add persiste e get_demand retorna corretamente."""
        thread_map.add("123", "login-oauth-a1b2")

        assert thread_map.get_demand("123") == "login-oauth-a1b2"

    def test_add_e_get_thread(self, thread_map):
        """Verifica mapeamento bidirecional demand → thread."""
        thread_map.add("456", "dashboard-metr-z3")

        assert thread_map.get_thread("dashboard-metr-z3") == "456"

    def test_get_demand_inexistente(self, thread_map):
        """Retorna None para thread_id não mapeado."""
        assert thread_map.get_demand("999") is None

    def test_get_thread_inexistente(self, thread_map):
        """Retorna None para demand_id não mapeado."""
        assert thread_map.get_thread("inexistente") is None

    def test_multiplos_mapeamentos(self, thread_map):
        """Suporta múltiplos mapeamentos simultâneos."""
        thread_map.add("100", "demanda-a")
        thread_map.add("200", "demanda-b")
        thread_map.add("300", "demanda-c")

        assert thread_map.get_demand("100") == "demanda-a"
        assert thread_map.get_demand("200") == "demanda-b"
        assert thread_map.get_demand("300") == "demanda-c"
        assert thread_map.get_thread("demanda-b") == "200"

    def test_persistencia_em_disco(self, state_dir):
        """Mapeamento sobrevive a recarregamento."""
        # Cria e adiciona
        tm1 = ThreadDemandMap(state_dir=state_dir)
        tm1.add("123", "login-oauth-a1b2")
        tm1.add("456", "dashboard-z3")

        # Recarrega de outro instância
        tm2 = ThreadDemandMap(state_dir=state_dir)

        assert tm2.get_demand("123") == "login-oauth-a1b2"
        assert tm2.get_demand("456") == "dashboard-z3"
        assert tm2.get_thread("login-oauth-a1b2") == "123"

    def test_arquivo_json_formato_correto(self, state_dir, thread_map):
        """Verifica formato do arquivo JSON persistido."""
        thread_map.add("123", "login-a1b2")

        json_path = state_dir / "thread-demands.json"
        assert json_path.exists()

        with open(json_path) as f:
            data = json.load(f)

        assert "thread_to_demand" in data
        assert "demand_to_thread" in data
        assert data["thread_to_demand"]["123"] == "login-a1b2"
        assert data["demand_to_thread"]["login-a1b2"] == "123"

    def test_load_arquivo_inexistente(self, state_dir):
        """Load de arquivo inexistente não falha."""
        tm = ThreadDemandMap(state_dir=state_dir)
        assert tm.get_demand("1") is None

    def test_load_arquivo_corrompido(self, state_dir):
        """Load de arquivo corrompido não falha."""
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "thread-demands.json").write_text("{{invalid json")

        tm = ThreadDemandMap(state_dir=state_dir)
        assert tm.get_demand("1") is None
