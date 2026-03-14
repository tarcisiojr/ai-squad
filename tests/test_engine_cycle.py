"""Testes para o ciclo completo do motor de orquestração."""

from unittest.mock import AsyncMock

import pytest

from src.models import DemandState, AgentStatus
from src.orchestrator.engine import OrchestrationEngine
from src.orchestrator.state import StateManager
from src.adapters.interface import AIAgentAdapter
from src.barramento.interface import MessageBus


class CycleAdapter(AIAgentAdapter):
    """Adapter para teste de ciclo completo."""

    def __init__(self):
        self._status = AgentStatus.IDLE
        self._callback = None

    async def run(self, prompt: str, context: dict) -> str:
        self._status = AgentStatus.RUNNING
        resultado = f"ok:{context.get('agent_name', '')}"
        self._status = AgentStatus.DONE
        return resultado

    async def ask(self, question: str) -> str:
        return "sim"

    def status(self) -> AgentStatus:
        return self._status

    def on_human_needed(self, callback):
        self._callback = callback


class CycleBus(MessageBus):
    """MessageBus para teste de ciclo."""

    def __init__(self):
        self.mensagens = []
        self.notificacoes = []

    async def send_message(self, user_id: str, text: str) -> None:
        self.mensagens.append((user_id, text))

    async def send_approval_request(
        self, user_id: str, question: str, options: list[str]
    ) -> str:
        return "Aprovar"

    async def receive_message(self, callback) -> None:
        pass

    async def receive_voice(self, callback) -> None:
        pass

    async def notify(self, user_id: str, text: str) -> None:
        self.notificacoes.append((user_id, text))


class TestRunDemandCycle:
    """Testes para o ciclo completo run_demand_cycle."""

    @pytest.mark.asyncio
    async def test_ciclo_completo_aprovado(self, tmp_path):
        """Verifica ciclo completo quando tudo é aprovado."""
        adapter = CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        engine = OrchestrationEngine(adapter, bus, state_mgr)

        await engine.run_demand_cycle("cycle-1", "user1", "Criar feature X")

        assert engine.get_state("cycle-1") == DemandState.DONE
        # Verifica que notificações foram enviadas
        assert len(bus.notificacoes) >= 4

    @pytest.mark.asyncio
    async def test_ciclo_rejeita_plano(self, tmp_path):
        """Verifica que rejeição do plano para o ciclo."""
        adapter = CycleAdapter()

        class BusRejeita(CycleBus):
            async def send_approval_request(self, user_id, question, options):
                return "Rejeitar"

        bus = BusRejeita()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        engine = OrchestrationEngine(adapter, bus, state_mgr)

        await engine.run_demand_cycle("cycle-rej", "user1", "Feature Y")

        # Parou em awaiting_plan_approval (não avançou para dev_working)
        assert engine.get_state("cycle-rej") == DemandState.AWAITING_PLAN_APPROVAL

    @pytest.mark.asyncio
    async def test_ciclo_rejeita_pr(self, tmp_path):
        """Verifica que rejeição do PR para o ciclo."""
        adapter = CycleAdapter()
        chamadas = [0]

        class BusRejeitaPR(CycleBus):
            async def send_approval_request(self, user_id, question, options):
                chamadas[0] += 1
                # Aprova plano (1a chamada), rejeita PR (2a chamada)
                return "Aprovar" if chamadas[0] == 1 else "Rejeitar"

        bus = BusRejeitaPR()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        engine = OrchestrationEngine(adapter, bus, state_mgr)

        await engine.run_demand_cycle("cycle-pr-rej", "user1", "Feature Z")

        assert engine.get_state("cycle-pr-rej") == DemandState.AWAITING_PR_APPROVAL
