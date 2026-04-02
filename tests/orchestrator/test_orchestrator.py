"""Testes para o motor de orquestração."""

from unittest.mock import AsyncMock

import pytest

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.messaging.interface import MessageBus
from ai_squad.models import AgentStatus
from ai_squad.orchestrator.engine import OrchestrationEngine
from ai_squad.orchestrator.state import StateManager


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

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    @classmethod
    def required_env_vars(cls) -> list[str]:
        return []

    @classmethod
    def env_template(cls) -> str:
        return ""

    async def send_message(self, user_id: str, text: str, **kwargs) -> None:
        await self._send_message_mock(user_id, text)

    async def send_approval_request(self, user_id: str, question: str, options: list[str]) -> str:
        return await self._send_approval_mock(user_id=user_id, question=question, options=options)

    async def receive_message(self, callback) -> None:
        await self._receive_message_mock(callback)

    async def receive_voice(self, callback) -> None:
        await self._receive_voice_mock(callback)

    async def ask_user(self, user_id: str, question: str) -> str:
        return "resposta do usuário"

    async def notify(self, user_id: str, text: str) -> None:
        await self._notify_mock(user_id, text)


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

        await engine.dispatch_agent("demand-1", "po", "prompt", {"chave": "valor"})

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
