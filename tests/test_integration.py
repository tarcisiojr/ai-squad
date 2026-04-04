"""Testes de integração para fluxo completo."""

import importlib
import inspect

import pytest

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.factory import PlatformConfig, PlatformFactory
from ai_squad.messaging.cli import CLIMessageBus
from ai_squad.messaging.interface import MessageBus
from ai_squad.models import AgentStatus
from ai_squad.orchestrator.engine import OrchestrationEngine
from ai_squad.orchestrator.state import StateManager


# Mock adapter para testes de integração
class IntegrationMockAdapter(AIAgentAdapter):
    """Adapter mock que simula execução de agentes."""

    def __init__(self):
        super().__init__()
        self._status = AgentStatus.IDLE
        self._callback = None

    async def run(self, prompt: str, context: dict) -> str:
        self._status = AgentStatus.RUNNING
        resultado = f"Resultado para: {context.get('agent_name', 'unknown')}"
        self._status = AgentStatus.DONE
        return resultado

    async def ask(self, question: str) -> str:
        return "resposta integração"

    def status(self) -> AgentStatus:
        return self._status

    def on_human_needed(self, callback):
        self._callback = callback


class TestFluxoCompleto:
    """Teste de integração: fluxo com dispatch de agentes."""

    @pytest.mark.asyncio
    async def test_dispatch_agentes_com_cli_bus(self, tmp_path):
        """Verifica dispatch de agentes com CLIMessageBus + mock adapter."""
        adapter = IntegrationMockAdapter()
        bus = CLIMessageBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))

        engine = OrchestrationEngine(adapter, bus, state_mgr)

        demand_id = "integ-001"

        # PO produz resultado
        resultado = await engine.dispatch_agent(demand_id, "po", "Nova feature", {"repo": "test"})
        assert "po" in resultado

        # Dev produz resultado
        resultado_dev = await engine.dispatch_agent(
            demand_id, "dev-orchestrator", "Implementar", {}
        )
        assert "dev-orchestrator" in resultado_dev

        # QA valida
        resultado_qa = await engine.dispatch_agent(demand_id, "qa", "Validar", {})
        assert "qa" in resultado_qa

    @pytest.mark.asyncio
    async def test_estado_persiste_entre_instancias(self, tmp_path):
        """Verifica que estado persiste via StateManager entre instâncias."""
        state_dir = str(tmp_path / "state")

        # Primeira instância — grava estado diretamente no StateManager
        state_mgr1 = StateManager(state_dir=state_dir)
        state_mgr1.set_state("demand-persist", "awaiting_plan_approval")

        # Segunda instância (simula reinício)
        state_mgr2 = StateManager(state_dir=state_dir)
        assert state_mgr2.get_state("demand-persist") == "awaiting_plan_approval"


class TestTrocaDeProvider:
    """Teste de integração: troca de provider via platform.yaml."""

    def test_troca_messaging_provider(self, tmp_path):
        """Verifica que trocar messaging_provider no config funciona."""
        factory = PlatformFactory()
        factory.register_message_bus("cli", CLIMessageBus)

        config = PlatformConfig(
            ai_provider="claude-code",
            messaging_provider="cli",
        )

        bus = factory.create_message_bus(config)
        assert isinstance(bus, CLIMessageBus)
        assert isinstance(bus, MessageBus)

    def test_troca_ai_provider(self, tmp_path):
        """Verifica que trocar ai_provider no config funciona."""
        factory = PlatformFactory()
        factory.register_ai_adapter("mock", IntegrationMockAdapter)

        config = PlatformConfig(
            ai_provider="mock",
            messaging_provider="cli",
        )

        adapter = factory.create_ai_adapter(config)
        assert isinstance(adapter, IntegrationMockAdapter)
        assert isinstance(adapter, AIAgentAdapter)

    def test_config_completa_via_yaml(self, tmp_path):
        """Verifica carregamento completo via YAML e instanciação."""
        import yaml

        config_file = tmp_path / "platform.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "mock",
                    "messaging_provider": "cli",
                    "agent_timeout": 120,
                }
            )
        )

        config = PlatformConfig.from_yaml(config_file)
        factory = PlatformFactory()
        factory.register_message_bus("cli", CLIMessageBus)
        factory.register_ai_adapter("mock", IntegrationMockAdapter)

        bus = factory.create_message_bus(config)
        adapter = factory.create_ai_adapter(config)

        assert isinstance(bus, MessageBus)
        assert isinstance(adapter, AIAgentAdapter)
        assert config.agent_timeout == 120


class TestDesacoplamento:
    """Testes de validação de desacoplamento."""

    def test_orchestrator_nao_importa_implementacao_concreta(self):
        """Verifica que o orquestrador não importa implementações concretas."""
        modulo = importlib.import_module("ai_squad.orchestrator.engine")
        source = inspect.getsource(modulo)

        # Não deve importar implementações concretas
        assert "from ai_squad.messaging.cli" not in source
        assert "from ai_squad.messaging.telegram" not in source
        assert "from ai_squad.adapters.claude_code" not in source
        assert "CLIMessageBus" not in source
        assert "TelegramMessageBus" not in source
        assert "ClaudeCodeAdapter" not in source

    def test_factory_eh_unico_ponto_de_conhecimento(self):
        """Verifica que apenas factory e testes conhecem implementações."""
        modulos_core = [
            "ai_squad.orchestrator.engine",
            "ai_squad.orchestrator.state",
            "ai_squad.models",
            "ai_squad.messaging.interface",
            "ai_squad.adapters.interface",
        ]

        for nome_modulo in modulos_core:
            modulo = importlib.import_module(nome_modulo)
            source = inspect.getsource(modulo)
            # Módulos core não devem importar implementações concretas
            assert "ClaudeCodeAdapter" not in source, f"{nome_modulo} importa ClaudeCodeAdapter"
            assert "TelegramMessageBus" not in source, f"{nome_modulo} importa TelegramMessageBus"
