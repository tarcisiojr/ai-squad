"""Testes unitários para interfaces ABC e enums."""

import pytest

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.messaging.interface import MessageBus
from ai_squad.models import AgentStatus


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
            def __init__(self):
                super().__init__()

        with pytest.raises(TypeError):
            AdapterIncompleto()
