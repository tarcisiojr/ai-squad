"""Testes unitários para interfaces ABC e enums."""

import pytest

from src.models import AgentStatus, DemandState, VALID_TRANSITIONS
from src.barramento.interface import MessageBus
from src.adapters.interface import AIAgentAdapter


class TestAgentStatus:
    """Testes para o enum AgentStatus."""

    def test_valores_existem(self):
        """Verifica que todos os status esperados existem."""
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.WAITING_HUMAN.value == "waiting_human"
        assert AgentStatus.ERROR.value == "error"
        assert AgentStatus.DONE.value == "done"

    def test_total_de_status(self):
        """Verifica que existem exatamente 5 status."""
        assert len(AgentStatus) == 5

    def test_criacao_por_valor(self):
        """Verifica criação de enum por valor string."""
        assert AgentStatus("idle") == AgentStatus.IDLE
        assert AgentStatus("running") == AgentStatus.RUNNING

    def test_valor_invalido_levanta_erro(self):
        """Verifica que valor inválido levanta ValueError."""
        with pytest.raises(ValueError):
            AgentStatus("inexistente")


class TestDemandState:
    """Testes para o enum DemandState."""

    def test_valores_existem(self):
        """Verifica que todos os estados esperados existem."""
        assert DemandState.IDLE.value == "idle"
        assert DemandState.PO_WORKING.value == "po_working"
        assert DemandState.AWAITING_PLAN_APPROVAL.value == "awaiting_plan_approval"
        assert DemandState.DEV_WORKING.value == "dev_working"
        assert DemandState.AWAITING_PR_APPROVAL.value == "awaiting_pr_approval"
        assert DemandState.CI_RUNNING.value == "ci_running"
        assert DemandState.QA_VALIDATING.value == "qa_validating"
        assert DemandState.DONE.value == "done"

    def test_total_de_estados(self):
        """Verifica que existem exatamente 8 estados."""
        assert len(DemandState) == 8

    def test_criacao_por_valor(self):
        """Verifica criação de enum por valor string."""
        assert DemandState("idle") == DemandState.IDLE
        assert DemandState("done") == DemandState.DONE


class TestValidTransitions:
    """Testes para as transições válidas de estado."""

    def test_idle_transiciona_para_po_working(self):
        """Verifica que idle só vai para po_working."""
        assert VALID_TRANSITIONS[DemandState.IDLE] == [DemandState.PO_WORKING]

    def test_done_nao_tem_transicao(self):
        """Verifica que done é estado final."""
        assert VALID_TRANSITIONS[DemandState.DONE] == []

    def test_todos_estados_tem_transicao_definida(self):
        """Verifica que todos os estados têm transições definidas."""
        for state in DemandState:
            assert state in VALID_TRANSITIONS

    def test_ciclo_completo_valido(self):
        """Verifica que o ciclo completo de transições é válido."""
        ciclo = [
            DemandState.IDLE,
            DemandState.PO_WORKING,
            DemandState.AWAITING_PLAN_APPROVAL,
            DemandState.DEV_WORKING,
            DemandState.AWAITING_PR_APPROVAL,
            DemandState.CI_RUNNING,
            DemandState.QA_VALIDATING,
            DemandState.DONE,
        ]
        for i in range(len(ciclo) - 1):
            atual = ciclo[i]
            proximo = ciclo[i + 1]
            assert proximo in VALID_TRANSITIONS[atual], (
                f"Transição {atual} → {proximo} deveria ser válida"
            )


class TestMessageBusABC:
    """Testes para a interface abstrata MessageBus."""

    def test_nao_pode_instanciar_diretamente(self):
        """Verifica que MessageBus não pode ser instanciado."""
        with pytest.raises(TypeError):
            MessageBus()

    def test_subclasse_sem_implementacao_falha(self):
        """Verifica que subclasse sem implementar métodos falha."""

        class BarramentoIncompleto(MessageBus):
            pass

        with pytest.raises(TypeError):
            BarramentoIncompleto()


class TestAIAgentAdapterABC:
    """Testes para a interface abstrata AIAgentAdapter."""

    def test_nao_pode_instanciar_diretamente(self):
        """Verifica que AIAgentAdapter não pode ser instanciado."""
        with pytest.raises(TypeError):
            AIAgentAdapter()

    def test_subclasse_sem_implementacao_falha(self):
        """Verifica que subclasse sem implementar métodos falha."""

        class AdapterIncompleto(AIAgentAdapter):
            pass

        with pytest.raises(TypeError):
            AdapterIncompleto()
