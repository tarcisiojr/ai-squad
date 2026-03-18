"""Testes para funcionalidades de inteligência do engine."""


from src.adapters.interface import AIAgentAdapter
from src.factory import AgentConfig
from src.models import AgentStatus
from src.orchestrator.engine import OrchestrationEngine
from src.orchestrator.state import StateManager


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
    "po": AgentConfig(name="PO", avatar="📋", command="/po"),
    "dev": AgentConfig(name="Dev", avatar="🔧", command="/dev"),
    "qa": AgentConfig(name="QA", avatar="🧪", command="/qa"),
}


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
