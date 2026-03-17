"""Testes para o motor de orquestração."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import DemandState, AgentStatus
from src.orchestrator.engine import OrchestrationEngine, InvalidTransitionError
from src.orchestrator.state import StateManager
from src.adapters.interface import AIAgentAdapter
from src.barramento.interface import MessageBus


# Fixtures para mocks
class MockAdapter(AIAgentAdapter):
    """Mock do AIAgentAdapter para testes."""

    def __init__(self):
        self._status = AgentStatus.IDLE
        self._callback = None
        self._run_mock = AsyncMock(return_value="resultado mock")
        self._ask_mock = AsyncMock(return_value="resposta mock")

    async def run(self, prompt: str, context: dict) -> str:
        return await self._run_mock(prompt, context)

    async def ask(self, question: str) -> str:
        return await self._ask_mock(question)

    def status(self) -> AgentStatus:
        return self._status

    def on_human_needed(self, callback):
        self._callback = callback


class MockMessageBus(MessageBus):
    """Mock do MessageBus para testes."""

    def __init__(self):
        self._send_message_mock = AsyncMock()
        self._send_approval_mock = AsyncMock(return_value="Aprovar")
        self._receive_message_mock = AsyncMock()
        self._receive_voice_mock = AsyncMock()
        self._notify_mock = AsyncMock()

    async def send_message(self, user_id: str, text: str, **kwargs) -> None:
        await self._send_message_mock(user_id, text)

    async def send_approval_request(
        self, user_id: str, question: str, options: list[str]
    ) -> str:
        return await self._send_approval_mock(
            user_id=user_id, question=question, options=options
        )

    async def receive_message(self, callback) -> None:
        await self._receive_message_mock(callback)

    async def receive_voice(self, callback) -> None:
        await self._receive_voice_mock(callback)

    async def ask_user(self, user_id: str, question: str) -> str:
        return "resposta do usuário"

    async def notify(self, user_id: str, text: str) -> None:
        await self._notify_mock(user_id, text)


class TestStateMachine:
    """Testes para máquina de estados do orquestrador."""

    @pytest.fixture
    def engine(self, tmp_path):
        """Cria engine com mocks."""
        adapter = MockAdapter()
        bus = MockMessageBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir()
        return OrchestrationEngine(adapter, bus, state_mgr, workspace=workspace)

    def test_estado_inicial_idle(self, engine):
        """Verifica que estado inicial é IDLE."""
        state = engine.get_state("demand-1")
        assert state == DemandState.IDLE

    def test_transicao_valida_idle_para_po_working(self, engine):
        """Verifica transição válida idle → po_working."""
        engine.transition("demand-1", DemandState.PO_WORKING)
        assert engine.get_state("demand-1") == DemandState.PO_WORKING

    def test_transicao_invalida_idle_para_dev_working(self, engine):
        """Verifica que transição inválida levanta erro."""
        with pytest.raises(InvalidTransitionError, match="Transição inválida"):
            engine.transition("demand-1", DemandState.DEV_WORKING)

    def test_transicao_invalida_done_para_qualquer(self, engine):
        """Verifica que done é estado terminal."""
        # Avança até done
        engine.transition("demand-1", DemandState.PO_WORKING)
        engine.transition("demand-1", DemandState.AWAITING_PLAN_APPROVAL)
        engine.transition("demand-1", DemandState.DEV_WORKING)
        engine.transition("demand-1", DemandState.AWAITING_PR_APPROVAL)
        engine.transition("demand-1", DemandState.CI_RUNNING)
        engine.transition("demand-1", DemandState.QA_VALIDATING)
        engine.transition("demand-1", DemandState.DONE)

        with pytest.raises(InvalidTransitionError):
            engine.transition("demand-1", DemandState.IDLE)

    def test_ciclo_completo(self, engine):
        """Verifica ciclo completo idle → done."""
        demand_id = "demand-ciclo"
        estados = [
            DemandState.PO_WORKING,
            DemandState.AWAITING_PLAN_APPROVAL,
            DemandState.DEV_WORKING,
            DemandState.AWAITING_PR_APPROVAL,
            DemandState.CI_RUNNING,
            DemandState.QA_VALIDATING,
            DemandState.DONE,
        ]

        for estado in estados:
            engine.transition(demand_id, estado)
            assert engine.get_state(demand_id) == estado

    def test_demandas_independentes(self, engine):
        """Verifica que demandas têm estados independentes."""
        engine.transition("demand-a", DemandState.PO_WORKING)
        engine.transition("demand-b", DemandState.PO_WORKING)
        engine.transition("demand-b", DemandState.AWAITING_PLAN_APPROVAL)

        assert engine.get_state("demand-a") == DemandState.PO_WORKING
        assert engine.get_state("demand-b") == DemandState.AWAITING_PLAN_APPROVAL


class TestDispatchAgent:
    """Testes para despacho de agentes."""

    @pytest.fixture
    def setup(self, tmp_path):
        """Cria engine com mocks."""
        adapter = MockAdapter()
        bus = MockMessageBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        engine = OrchestrationEngine(adapter, bus, state_mgr)
        return engine, adapter, bus

    @pytest.mark.asyncio
    async def test_dispatch_agent(self, setup):
        """Verifica despacho de agente via adapter."""
        engine, adapter, _ = setup

        resultado = await engine.dispatch_agent(
            "demand-1", "po", "Criar feature X", {"repo": "projeto"}
        )

        assert resultado == "resultado mock"
        adapter._run_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_inclui_contexto(self, setup):
        """Verifica que contexto inclui demand_id e agent_name."""
        engine, adapter, _ = setup

        await engine.dispatch_agent(
            "demand-1", "po", "prompt", {"chave": "valor"}
        )

        call_args = adapter._run_mock.call_args
        context = call_args[0][1]
        assert context["demand_id"] == "demand-1"
        assert context["agent_name"] == "po"
        assert context["chave"] == "valor"


class TestHumanRouting:
    """Testes para roteamento de decisões humanas."""

    @pytest.fixture
    def setup(self, tmp_path):
        """Cria engine com mocks."""
        adapter = MockAdapter()
        bus = MockMessageBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        engine = OrchestrationEngine(adapter, bus, state_mgr)
        return engine, adapter, bus

    @pytest.mark.asyncio
    async def test_request_approval(self, setup):
        """Verifica que aprovação é roteada ao barramento."""
        engine, _, bus = setup

        resultado = await engine.request_approval(
            "demand-1", "user1", "Aprovar plano?", ["Sim", "Não"]
        )

        assert resultado == "Aprovar"
        bus._send_approval_mock.assert_called_once_with(
            user_id="user1",
            question="Aprovar plano?",
            options=["Sim", "Não"],
        )

    @pytest.mark.asyncio
    async def test_notify_user(self, setup):
        """Verifica que notificação é enviada ao barramento."""
        engine, _, bus = setup

        await engine.notify_user("user1", "Tarefa concluída")

        bus._notify_mock.assert_called_once_with("user1", "Tarefa concluída")

    @pytest.mark.asyncio
    async def test_handle_human_needed_via_callback(self, setup):
        """Verifica que callback de intervenção humana roteia ao barramento."""
        engine, adapter, bus = setup

        # O callback foi registrado no construtor
        assert adapter._callback is not None

        resultado = await adapter._callback("Preciso de aprovação")
        assert resultado == "Aprovar"
        bus._send_approval_mock.assert_called_once()
