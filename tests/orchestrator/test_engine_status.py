"""Testes para EngineStatus e API pública do engine."""

import time

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.factory import AgentConfig
from ai_squad.models import AgentStatus
from ai_squad.orchestrator.engine import EngineStatus, OrchestrationEngine
from ai_squad.orchestrator.state import StateManager
from ai_squad.orchestrator.tools import RunningAgent


class MockAdapter(AIAgentAdapter):
    """Adapter mock para testes."""

    def __init__(self):
        super().__init__()
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
}


def _make_engine(tmp_path):
    """Cria engine com mocks para testes."""
    adapter = MockAdapter()
    bus = MockBus()
    state_mgr = StateManager(state_dir=str(tmp_path / "state"))
    workspace = str(tmp_path / "workspace")
    (tmp_path / "workspace").mkdir(exist_ok=True)
    return OrchestrationEngine(
        adapter,
        bus,
        state_mgr,
        workspace=workspace,
        personas=TEST_PERSONAS,
    )


class TestEngineStatus:
    """Testes para o dataclass EngineStatus."""

    def test_defaults(self):
        """EngineStatus tem defaults corretos."""
        status = EngineStatus()
        assert status.squad_lead_busy is False
        assert status.squad_lead_since == 0.0
        assert status.current_demand_id == ""
        assert status.running_agents == {}
        assert status.personas == {}
        assert status.token_summary == ""

    def test_com_valores(self):
        """EngineStatus aceita valores customizados."""
        now = time.time()
        status = EngineStatus(
            squad_lead_busy=True,
            squad_lead_since=now,
            current_demand_id="d-123",
            running_agents={"dev": "running"},
            personas={"po": "PO"},
        )
        assert status.squad_lead_busy is True
        assert status.squad_lead_since == now
        assert status.current_demand_id == "d-123"
        assert status.running_agents == {"dev": "running"}
        assert status.personas == {"po": "PO"}


class TestGetStatus:
    """Testes para engine.get_status()."""

    def test_retorna_status_idle(self, tmp_path):
        """get_status() retorna valores iniciais quando engine está idle."""
        engine = _make_engine(tmp_path)
        status = engine.get_status()

        assert isinstance(status, EngineStatus)
        assert status.squad_lead_busy is False
        assert status.current_demand_id == ""
        assert status.running_agents == {}
        assert len(status.personas) == 2  # po + dev

    def test_retorna_status_busy(self, tmp_path):
        """get_status() reflete estado busy do Squad Lead."""
        engine = _make_engine(tmp_path)
        engine._squad_lead_busy = True
        engine._squad_lead_busy_since = time.time()
        engine._default_demand_id = "test-demand"

        status = engine.get_status()

        assert status.squad_lead_busy is True
        assert status.squad_lead_since > 0
        assert status.current_demand_id == "test-demand"

    def test_retorna_copia_running_agents(self, tmp_path):
        """get_status() retorna cópia do dict de running_agents."""
        engine = _make_engine(tmp_path)
        status = engine.get_status()

        # Modificar o dict retornado não afeta o engine
        status.running_agents["fake"] = "test"
        assert "fake" not in engine.get_status().running_agents


class TestPublicSetters:
    """Testes para setters públicos do engine."""

    def test_set_thread_map(self, tmp_path):
        """set_thread_map() injeta mapeamento no engine."""
        engine = _make_engine(tmp_path)
        mock_map = {"thread-1": "demand-1"}
        engine.set_thread_map(mock_map)
        assert engine._thread_map == mock_map

    def test_set_create_topic_callback(self, tmp_path):
        """set_create_topic_callback() injeta callback no engine."""
        engine = _make_engine(tmp_path)

        async def _cb(demand_id, title):
            return "thread-123"

        engine.set_create_topic_callback(_cb)
        assert engine._create_topic_callback == _cb


class TestGetJournal:
    """Testes para engine.get_journal()."""

    def test_retorna_journal_store(self, tmp_path):
        """get_journal() retorna instância de JournalStore."""
        engine = _make_engine(tmp_path)
        journal = engine.get_journal()

        assert journal is not None
        # Deve ser o mesmo objeto
        assert journal is engine._journal


class TestGetRunningAgentsStatus:
    """Testes para engine.get_running_agents_status() (API pública)."""

    def test_sem_agentes(self, tmp_path):
        """Retorna mensagem padrão quando nenhum agente ativo."""
        engine = _make_engine(tmp_path)
        status = engine.get_running_agents_status()
        assert "Nenhum" in status

    def test_com_squad_lead_busy(self, tmp_path):
        """Inclui Squad Lead no status quando ocupado."""
        engine = _make_engine(tmp_path)
        engine._squad_lead_busy = True
        engine._squad_lead_busy_since = time.time()

        status = engine.get_running_agents_status()
        assert "processando" in status


class TestStopAgent:
    """Testes para engine.stop_agent()."""

    def test_para_agente_rodando(self, tmp_path):
        """stop_agent() cancela task e muda status."""
        engine = _make_engine(tmp_path)
        from unittest.mock import MagicMock

        mock_task = MagicMock()
        engine._running_agents["dev"] = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="u1",
            status="running",
            task=mock_task,
        )

        result = engine.stop_agent("dev")
        assert result is True
        mock_task.cancel.assert_called_once()
        assert engine._running_agents["dev"].status == "cancelled"

    def test_agente_inexistente(self, tmp_path):
        """stop_agent() retorna False para agente inexistente."""
        engine = _make_engine(tmp_path)
        result = engine.stop_agent("inexistente")
        assert result is False

    def test_agente_nao_rodando(self, tmp_path):
        """stop_agent() retorna False para agente que não está rodando."""
        engine = _make_engine(tmp_path)
        engine._running_agents["dev"] = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="u1",
            status="done",
            task=None,
        )

        result = engine.stop_agent("dev")
        assert result is False


class TestGetAgentLabel:
    """Testes para engine.get_agent_label()."""

    def test_retorna_label(self, tmp_path):
        """get_agent_label() retorna nome formatado do agente."""
        engine = _make_engine(tmp_path)
        label = engine.get_agent_label("po")
        assert "PO" in label
