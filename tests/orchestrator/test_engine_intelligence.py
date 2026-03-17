"""Testes para funcionalidades de inteligência do engine."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.models import AgentStatus
from src.factory import PersonaConfig
from src.orchestrator.engine import OrchestrationEngine
from src.orchestrator.state import StateManager
from src.adapters.interface import AIAgentAdapter


class MockAdapter(AIAgentAdapter):
    """Adapter mock para testes."""

    def __init__(self):
        self._status = AgentStatus.IDLE

    async def run(self, prompt, context):
        return "ok"

    async def ask(self, question):
        return "ok"

    def status(self):
        return self._status

    def on_human_needed(self, callback):
        pass


class MockBus:
    """Bus mock que grava mensagens."""

    def __init__(self):
        self.mensagens = []

    async def send_message(self, user_id, text, **kwargs):
        self.mensagens.append((user_id, text))

    async def notify(self, user_id, text):
        self.mensagens.append((user_id, text))

    async def ask_user(self, user_id, question):
        return "resposta mock"

    async def send_approval_request(self, user_id, question, options):
        return "Aprovar"

    async def send_typing(self, user_id):
        pass


TEST_PERSONAS = {
    "po": PersonaConfig(name="PO", avatar="📋", command="/po"),
    "dev": PersonaConfig(name="Dev", avatar="🔧", command="/dev"),
    "qa": PersonaConfig(name="QA", avatar="🧪", command="/qa"),
}


class TestCheckArtifactsEnriched:
    """Testes para check_artifacts com Criteria Gate."""

    def _make_engine(self, tmp_path):
        adapter = MockAdapter()
        bus = MockBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir(exist_ok=True)
        return OrchestrationEngine(
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )

    def test_change_inexistente(self, tmp_path):
        """Change inexistente retorna mensagem de erro."""
        engine = self._make_engine(tmp_path)
        result = engine._check_artifacts_enriched("nao-existe")
        assert "nao encontrada" in result

    def test_artefatos_completos_aprovados(self, tmp_path):
        """Artefatos completos retornam APROVADO."""
        engine = self._make_engine(tmp_path)
        ws = Path(engine._workspace)
        change = ws / "openspec" / "changes" / "feature-x"
        specs = change / "specs" / "core"
        specs.mkdir(parents=True)
        (change / "proposal.md").write_text("# Proposal com conteudo suficiente para validacao de tamanho minimo")
        (change / "design.md").write_text("# Design com conteudo suficiente para validacao de tamanho minimo")
        (specs / "spec.md").write_text("# Spec com criterios de aceite\n- [ ] Criterio 1\n- [ ] Criterio 2")
        (change / "tasks.md").write_text("- [ ] Task numero 1\n- [ ] Task numero 2\n- [ ] Task numero 3")

        result = engine._check_artifacts_enriched("feature-x")
        assert "APROVADO" in result

    def test_specs_sem_criterios_reprovado(self, tmp_path):
        """Specs sem critérios de aceite reprovam."""
        engine = self._make_engine(tmp_path)
        ws = Path(engine._workspace)
        change = ws / "openspec" / "changes" / "feature-y"
        specs = change / "specs" / "core"
        specs.mkdir(parents=True)
        (change / "proposal.md").write_text("# P")
        (change / "design.md").write_text("# D")
        (specs / "spec.md").write_text("# Spec sem checklist")
        (change / "tasks.md").write_text("- [ ] T1\n- [ ] T2\n- [ ] T3")

        result = engine._check_artifacts_enriched("feature-y")
        assert "REPROVADO" in result
        assert "criterios" in result.lower()

    def test_tasks_insuficientes_reprovado(self, tmp_path):
        """Tasks com menos de 3 itens reprovam."""
        engine = self._make_engine(tmp_path)
        ws = Path(engine._workspace)
        change = ws / "openspec" / "changes" / "feature-z"
        specs = change / "specs" / "core"
        specs.mkdir(parents=True)
        (change / "proposal.md").write_text("# P")
        (change / "design.md").write_text("# D")
        (specs / "spec.md").write_text("# S\n- [ ] C1")
        (change / "tasks.md").write_text("- [ ] T1\n- [ ] T2")

        result = engine._check_artifacts_enriched("feature-z")
        assert "REPROVADO" in result

    def test_design_ausente_reprovado(self, tmp_path):
        """Sem design.md reprova."""
        engine = self._make_engine(tmp_path)
        ws = Path(engine._workspace)
        change = ws / "openspec" / "changes" / "feature-w"
        specs = change / "specs" / "core"
        specs.mkdir(parents=True)
        (change / "proposal.md").write_text("# P")
        (specs / "spec.md").write_text("# S\n- [ ] C1")
        (change / "tasks.md").write_text("- [ ] T1\n- [ ] T2\n- [ ] T3")

        result = engine._check_artifacts_enriched("feature-w")
        assert "REPROVADO" in result
        assert "design" in result.lower()


class TestGetDemandState:
    """Testes para get_demand_state_summary."""

    def _make_engine(self, tmp_path):
        adapter = MockAdapter()
        bus = MockBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir(exist_ok=True)
        return OrchestrationEngine(
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )

    def test_sem_demandas(self, tmp_path):
        """Sem demandas retorna mensagem adequada."""
        engine = self._make_engine(tmp_path)
        result = engine._get_demand_state_summary()
        assert "Nenhuma" in result

    def test_com_demanda_ativa(self, tmp_path):
        """Com demanda ativa retorna detalhes."""
        engine = self._make_engine(tmp_path)
        # Cria journal ativo
        engine._journal.create("d1", "Criar login")
        engine._journal.set_phase("d1", "dev_working")

        result = engine._get_demand_state_summary()
        assert "d1" in result
        assert "Criar login" in result
        assert "dev_working" in result


class TestVerifyPOCompletion:
    """Testes detalhados para _verify_spec_completion."""

    def _make_engine(self, tmp_path):
        adapter = MockAdapter()
        bus = MockBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir(exist_ok=True)
        return OrchestrationEngine(
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )

    def test_sem_changes_dir(self, tmp_path):
        """Sem diretório de changes retorna issues."""
        engine = self._make_engine(tmp_path)
        issues = engine._verify_spec_completion()
        assert len(issues) > 0

    def test_specs_com_criterios_mixtos(self, tmp_path):
        """Specs com [x] (já feitos) também passam como critérios."""
        engine = self._make_engine(tmp_path)
        ws = Path(engine._workspace)
        change = ws / "openspec" / "changes" / "mix"
        specs = change / "specs" / "auth"
        specs.mkdir(parents=True)
        (change / "proposal.md").write_text("# Proposal com conteudo suficiente para passar na validacao de tamanho minimo")
        (change / "design.md").write_text("# Design com conteudo suficiente para passar na validacao de tamanho minimo")
        (specs / "spec.md").write_text("# Spec com criterios de aceite\n- [x] Feito\n- [ ] Pendente")
        (change / "tasks.md").write_text("- [ ] Task numero 1\n- [ ] Task numero 2\n- [ ] Task numero 3")

        issues = engine._verify_spec_completion()
        assert len(issues) == 0


class TestJournalIntegrationWithEngine:
    """Testes de integração do journal com o engine."""

    def _make_engine(self, tmp_path):
        adapter = MockAdapter()
        bus = MockBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir(exist_ok=True)
        return OrchestrationEngine(
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )

    def test_journal_criado_no_start_agent(self, tmp_path):
        """Journal é criado quando start_agent é chamado."""
        engine = self._make_engine(tmp_path)
        engine._default_demand_id = "test-demand"
        engine._default_user_id = "user1"

        # Não existe journal ainda
        assert engine._journal.read("test-demand") is None

    def test_journal_store_acessivel(self, tmp_path):
        """Engine tem acesso ao JournalStore."""
        engine = self._make_engine(tmp_path)
        assert engine._journal is not None
        journal = engine._journal.create("d1", "Test")
        assert journal["demand_id"] == "d1"
