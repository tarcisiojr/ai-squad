"""Testes para JournalStore — persistência de decisões do Squad Lead."""

import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from ai_squad.orchestrator.journal import JournalStore


class TestJournalCRUD:
    """Testes de operações básicas do journal."""

    @pytest.fixture
    def store(self, tmp_path):
        """Cria JournalStore com diretório temporário."""
        return JournalStore(state_dir=str(tmp_path))

    def test_create_journal(self, store):
        """Verifica criação de journal para nova demanda."""
        journal = store.create("demand-001", "Criar endpoint de login")

        assert journal["demand_id"] == "demand-001"
        assert journal["demand_text"] == "Criar endpoint de login"
        assert journal["current_phase"] == "idle"
        assert journal["decisions"] == []
        assert journal["next_expected"] is None
        assert journal["context_notes"] == []
        assert journal["auto_retries"] == 0
        assert "created_at" in journal
        assert "updated_at" in journal

    def test_read_journal(self, store):
        """Verifica leitura de journal existente."""
        store.create("demand-002", "Criar API")
        journal = store.read("demand-002")

        assert journal is not None
        assert journal["demand_id"] == "demand-002"

    def test_read_inexistente_retorna_none(self, store):
        """Verifica que leitura de journal inexistente retorna None."""
        assert store.read("nao-existe") is None

    def test_add_decision(self, store):
        """Verifica adição de decisão ao journal."""
        store.create("demand-003", "Feature X")
        store.add_decision("demand-003", "delegated_to_po", "Delegado ao PO para especificar")

        journal = store.read("demand-003")
        assert len(journal["decisions"]) == 1
        assert journal["decisions"][0]["action"] == "delegated_to_po"
        assert journal["decisions"][0]["detail"] == "Delegado ao PO para especificar"
        assert "timestamp" in journal["decisions"][0]

    def test_multiple_decisions(self, store):
        """Verifica adição de múltiplas decisões."""
        store.create("demand-004", "Feature Y")
        store.add_decision("demand-004", "delegated_to_po", "Passo 1")
        store.add_decision("demand-004", "artifacts_validated", "Passo 2")
        store.add_decision("demand-004", "delegated_to_dev", "Passo 3")

        journal = store.read("demand-004")
        assert len(journal["decisions"]) == 3
        assert journal["decisions"][2]["action"] == "delegated_to_dev"

    def test_set_next_expected(self, store):
        """Verifica definição de próxima ação esperada."""
        store.create("demand-005", "Feature Z")
        store.set_next_expected(
            "demand-005",
            "dev_completion",
            "dev",
            "Dev implementando 5 tasks",
        )

        journal = store.read("demand-005")
        assert journal["next_expected"]["action"] == "dev_completion"
        assert journal["next_expected"]["agent"] == "dev"
        assert journal["next_expected"]["description"] == "Dev implementando 5 tasks"

    def test_set_phase(self, store):
        """Verifica atualização de fase."""
        store.create("demand-006", "Feature W")
        store.set_phase("demand-006", "po_working")

        journal = store.read("demand-006")
        assert journal["current_phase"] == "po_working"

    def test_add_context_note(self, store):
        """Verifica adição de nota de contexto."""
        store.create("demand-007", "Feature V")
        store.add_context_note("demand-007", "Usuário pediu JWT, não session-based")

        journal = store.read("demand-007")
        assert len(journal["context_notes"]) == 1
        assert "JWT" in journal["context_notes"][0]

    def test_increment_retries(self, store):
        """Verifica incremento de contador de retries."""
        store.create("demand-008", "Feature U")
        store.increment_retries("demand-008")
        store.increment_retries("demand-008")

        journal = store.read("demand-008")
        assert journal["auto_retries"] == 2

    def test_update_inexistente_retorna_none(self, store):
        """Verifica que update em journal inexistente retorna None."""
        result = store.add_decision("nao-existe", "acao", "detalhe")
        assert result is None

    def test_updated_at_muda_apos_operacao(self, store):
        """Verifica que updated_at é atualizado em cada operação."""
        store.create("demand-009", "Feature T")
        j1 = store.read("demand-009")

        time.sleep(0.01)  # Garante timestamp diferente
        store.add_decision("demand-009", "acao", "detalhe")
        j2 = store.read("demand-009")

        assert j2["updated_at"] >= j1["updated_at"]


class TestJournalAtomicWrite:
    """Testes de escrita atômica."""

    @pytest.fixture
    def store(self, tmp_path):
        return JournalStore(state_dir=str(tmp_path))

    def test_journal_sobrevive_como_arquivo_json(self, store, tmp_path):
        """Verifica que journal é JSON válido no disco."""
        store.create("demand-atomic", "Teste atomico")
        path = tmp_path / "demand-atomic" / "squad-lead-journal.json"

        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert data["demand_id"] == "demand-atomic"

    def test_diretorio_criado_automaticamente(self, store, tmp_path):
        """Verifica que diretório é criado se não existe."""
        store.create("novo-dir-test", "Teste dir")
        assert (tmp_path / "novo-dir-test").is_dir()


class TestJournalActiveAndStalled:
    """Testes de detecção de journals ativos e parados."""

    @pytest.fixture
    def store(self, tmp_path):
        return JournalStore(state_dir=str(tmp_path))

    def test_get_active_journals_vazio(self, store):
        """Verifica retorno vazio quando não há journals."""
        assert store.get_active_journals() == []

    def test_get_active_journals_filtra_idle_e_done(self, store):
        """Verifica que journals idle e done são filtrados."""
        store.create("d1", "Demanda 1")  # idle
        store.create("d2", "Demanda 2")
        store.set_phase("d2", "po_working")
        store.create("d3", "Demanda 3")
        store.set_phase("d3", "done")

        active = store.get_active_journals()
        assert len(active) == 1
        assert active[0]["demand_id"] == "d2"

    def test_get_active_summaries_formatado(self, store):
        """Verifica formatação do resumo de journals ativos."""
        store.create("d1", "Criar login")
        store.set_phase("d1", "dev_working")
        store.set_next_expected("d1", "dev_completion", "dev", "Implementando 5 tasks")

        summary = store.get_active_summaries()
        assert "d1" in summary
        assert "Criar login" in summary
        assert "dev_working" in summary
        assert "Implementando 5 tasks" in summary

    def test_get_active_summaries_vazio(self, store):
        """Verifica mensagem quando não há journals ativos."""
        assert store.get_active_summaries() == "Nenhuma demanda ativa."

    def test_get_stalled_detecta_demanda_parada(self, store):
        """Verifica detecção de demanda parada por timeout."""
        store.create("d-stalled", "Demanda parada")
        store.set_phase("d-stalled", "dev_working")

        # Simula updated_at de 1h atrás
        journal = store.read("d-stalled")
        old_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        journal["updated_at"] = old_time
        path = store._journal_path("d-stalled")
        with open(path, "w") as f:
            json.dump(journal, f)

        stalled = store.get_stalled(stall_timeout=1800)
        assert len(stalled) == 1
        assert stalled[0]["demand_id"] == "d-stalled"
        assert stalled[0]["stalled_seconds"] > 1800

    def test_get_stalled_ignora_approval_states(self, store):
        """Verifica que demandas em approval NÃO são consideradas paradas."""
        store.create("d-approval", "Demanda aprovação")
        store.set_phase("d-approval", "awaiting_plan_approval")

        # Simula updated_at antigo
        journal = store.read("d-approval")
        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        journal["updated_at"] = old_time
        path = store._journal_path("d-approval")
        with open(path, "w") as f:
            json.dump(journal, f)

        stalled = store.get_stalled(stall_timeout=1800)
        assert len(stalled) == 0

    def test_get_stalled_nao_detecta_demanda_recente(self, store):
        """Verifica que demanda atualizada recentemente NÃO é parada."""
        store.create("d-recent", "Demanda recente")
        store.set_phase("d-recent", "dev_working")

        stalled = store.get_stalled(stall_timeout=1800)
        assert len(stalled) == 0

    def test_get_pending_approvals(self, store):
        """Verifica detecção de aprovações pendentes há muito tempo."""
        store.create("d-pending", "Demanda pending")
        store.set_phase("d-pending", "awaiting_plan_approval")

        # Simula updated_at de 2h atrás
        journal = store.read("d-pending")
        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        journal["updated_at"] = old_time
        path = store._journal_path("d-pending")
        with open(path, "w") as f:
            json.dump(journal, f)

        pending = store.get_pending_approvals(reminder_timeout=3600)
        assert len(pending) == 1
        assert pending[0]["demand_id"] == "d-pending"
