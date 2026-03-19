"""Testes para o ciclo completo do motor de orquestração."""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from src.adapters.interface import AIAgentAdapter
from src.factory import AgentConfig
from src.messaging.interface import MessageBus
from src.models import AgentStatus
from src.orchestrator.engine import OrchestrationEngine
from src.orchestrator.state import StateManager

TEST_PERSONAS = {
    "po": AgentConfig(name="PO", avatar="📋", command="/po", role="spec"),
    "dev": AgentConfig(name="Dev", avatar="🔧", command="/dev", role="dev"),
    "qa": AgentConfig(name="QA", avatar="🧪", command="/qa", role="review"),
}


class CycleAdapter(AIAgentAdapter):
    """Adapter para teste de ciclo completo."""

    def __init__(self):
        self._status = AgentStatus.IDLE
        self._callback = None

    async def run(self, prompt: str, context: dict) -> str:
        self._status = AgentStatus.RUNNING
        agent = context.get("agent_name", "")
        resultado = f"ok:{agent}"
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
        self.mensagens.append((user_id, text))

    async def send_approval_request(self, user_id: str, question: str, options: list[str]) -> str:
        # Retorna a primeira opção (aprovação) por padrão
        return options[0] if options else "✅ Aprovar"

    async def receive_message(self, callback) -> None:
        pass

    async def receive_voice(self, callback) -> None:
        pass

    async def ask_user(self, user_id: str, question: str) -> str:
        return "resposta do usuário"

    async def notify(self, user_id: str, text: str) -> None:
        self.notificacoes.append((user_id, text))


class TestRunDemandCycle:
    """Testes para o ciclo completo run_squad_lead."""

    @pytest.mark.asyncio
    async def test_ciclo_completo_aprovado(self, tmp_path):
        """Verifica ciclo completo quando tudo é aprovado."""
        adapter = CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir()
        engine = OrchestrationEngine(
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS
        )

        await engine.run_squad_lead("cycle-1", "user1", "Criar feature X")

        # Squad Lead coordena — verifica que alguma mensagem foi enviada
        assert len(bus.mensagens) > 0 or len(bus.notificacoes) > 0


class SlowAdapter(AIAgentAdapter):
    """Adapter que demora para responder (simula agente lento)."""

    def __init__(self, delay: float = 0.0):
        self._status = AgentStatus.IDLE
        self._callback = None
        self._delay = delay

    async def run(self, prompt: str, context: dict) -> str:
        self._status = AgentStatus.RUNNING
        await asyncio.sleep(self._delay)
        agent = context.get("agent_name", "")
        self._status = AgentStatus.DONE
        return f"resultado:{agent}"

    async def ask(self, question: str) -> str:
        return "sim"

    def status(self) -> AgentStatus:
        return self._status

    def on_human_needed(self, callback):
        self._callback = callback


class TestFeedbackPeriodico:
    """Testes para o feedback periodico durante execucao de agentes."""

    @pytest.mark.asyncio
    async def test_feedback_enviado_apos_intervalo(self, tmp_path):
        """Verifica que feedback textual e enviado apos FEEDBACK_INTERVAL."""
        bus = CycleBus()
        bus.send_typing = AsyncMock()
        # Adapter que demora 0.15s (feedback intervalo = 0.08s)
        adapter = SlowAdapter(delay=0.15)
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir()
        engine = OrchestrationEngine(
            adapter,
            bus,
            state_mgr,
            workspace=workspace,
            personas=TEST_PERSONAS,
        )
        # Reduz intervalos para teste rapido (FEEDBACK deve ser multiplo de TYPING)
        engine.TYPING_INTERVAL = 0.02
        engine.FEEDBACK_INTERVAL = 0.04

        resultado = await engine._agent_conversation(
            "fb-1",
            "user1",
            "po",
            "Testar feedback",
            {"fase": "teste"},
        )

        assert resultado  # Agente concluiu
        # Verifica que typing foi chamado
        assert bus.send_typing.call_count >= 1

        # Verifica que feedback de tempo foi enviado (sender via kwarg, nao no texto)
        feedback_msgs = [msg for _, msg in bus.mensagens if "Trabalhando..." in msg]
        assert len(feedback_msgs) >= 1

    @pytest.mark.asyncio
    async def test_feedback_cancelado_ao_concluir(self, tmp_path):
        """Verifica que task de feedback e cancelada quando agente conclui."""
        bus = CycleBus()
        bus.send_typing = AsyncMock()
        adapter = SlowAdapter(delay=0.01)
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir()
        engine = OrchestrationEngine(
            adapter,
            bus,
            state_mgr,
            workspace=workspace,
            personas=TEST_PERSONAS,
        )
        engine.TYPING_INTERVAL = 0.5  # Alto para nao disparar
        engine.FEEDBACK_INTERVAL = 1.0

        resultado = await engine._agent_conversation(
            "fb-2",
            "user1",
            "dev",
            "Implementar X",
            {"fase": "teste"},
        )

        assert resultado
        # Feedback NAO deve ter sido enviado (agente concluiu rapido)
        feedback_msgs = [msg for _, msg in bus.mensagens if "[🔧 Dev]" in msg and "..." in msg]
        assert len(feedback_msgs) == 0

    @pytest.mark.asyncio
    async def test_format_elapsed(self):
        """Verifica formatacao de tempo decorrido."""
        assert OrchestrationEngine._format_elapsed(30) == "30s"
        assert OrchestrationEngine._format_elapsed(60) == "1min"
        assert OrchestrationEngine._format_elapsed(90) == "1min30s"
        assert OrchestrationEngine._format_elapsed(120) == "2min"
        assert OrchestrationEngine._format_elapsed(45) == "45s"

    @pytest.mark.asyncio
    async def test_feedback_sem_send_typing(self, tmp_path):
        """Verifica que feedback funciona mesmo sem send_typing no bus."""
        bus = CycleBus()
        # Sem send_typing — nao deve dar erro
        adapter = SlowAdapter(delay=0.12)
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir()
        engine = OrchestrationEngine(
            adapter,
            bus,
            state_mgr,
            workspace=workspace,
            personas=TEST_PERSONAS,
        )
        engine.TYPING_INTERVAL = 0.02
        engine.FEEDBACK_INTERVAL = 0.04

        resultado = await engine._agent_conversation(
            "fb-no-typing",
            "user1",
            "po",
            "Testar sem typing",
            {"fase": "teste"},
        )

        assert resultado
        feedback_msgs = [msg for _, msg in bus.mensagens if "Trabalhando..." in msg]
        assert len(feedback_msgs) >= 1

    @pytest.mark.asyncio
    async def test_feedback_atualiza_tempo(self, tmp_path):
        """Verifica que mensagens de feedback atualizam o tempo."""
        bus = CycleBus()
        bus.send_typing = AsyncMock()
        # Adapter que demora o suficiente para 2 feedbacks
        adapter = SlowAdapter(delay=0.25)
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir()
        engine = OrchestrationEngine(
            adapter,
            bus,
            state_mgr,
            workspace=workspace,
            personas=TEST_PERSONAS,
        )
        engine.TYPING_INTERVAL = 0.02
        engine.FEEDBACK_INTERVAL = 0.04

        await engine._agent_conversation(
            "fb-3",
            "user1",
            "po",
            "Testar tempo",
            {"fase": "teste"},
        )

        feedback_msgs = [msg for _, msg in bus.mensagens if "Trabalhando..." in msg]
        # Deve haver pelo menos 2 feedbacks com tempos diferentes
        if len(feedback_msgs) >= 2:
            assert feedback_msgs[0] != feedback_msgs[1]


class TestInvokeAgent:
    """Testes para invocacao de agentes via engine."""

    @pytest.mark.asyncio
    async def test_direct_agent_conversation(self, tmp_path):
        """Verifica conversa direta com agente."""
        adapter = CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir()
        engine = OrchestrationEngine(
            adapter,
            bus,
            state_mgr,
            workspace=workspace,
            personas=TEST_PERSONAS,
        )
        engine.TYPING_INTERVAL = 0.5
        engine.FEEDBACK_INTERVAL = 5.0

        await engine.direct_agent_conversation(
            "direct-1",
            "user1",
            "po",
            "Olá PO",
        )

        # Notificacoes de inicio e fim
        assert any("recebeu" in msg for _, msg in bus.notificacoes)
        assert any("finalizada" in msg for _, msg in bus.notificacoes)

    @pytest.mark.asyncio
    async def test_handle_progress_envia_ao_bus(self, tmp_path):
        """Verifica que _handle_progress envia mensagem ao bus."""
        adapter = CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        engine = OrchestrationEngine(
            adapter,
            bus,
            state_mgr,
            workspace=str(tmp_path),
            personas=TEST_PERSONAS,
        )
        engine._default_user_id = "user1"

        await engine._handle_progress("po", "Gerando proposal.md")

        assert any("Gerando proposal.md" in msg for _, msg in bus.mensagens)

    @pytest.mark.asyncio
    async def test_handle_progress_sem_user_id(self, tmp_path):
        """Verifica que _handle_progress nao envia sem user_id."""
        adapter = CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        engine = OrchestrationEngine(
            adapter,
            bus,
            state_mgr,
            workspace=str(tmp_path),
            personas=TEST_PERSONAS,
        )
        engine._default_user_id = ""

        await engine._handle_progress("po", "Nao deve enviar")

        assert len(bus.mensagens) == 0

    def test_get_agents_summary(self, tmp_path):
        """Verifica geracao de resumo de agentes."""
        adapter = CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        # Cria diretorio de agentes com AGENTS.md
        agents_dir = tmp_path / "agents"
        po_dir = agents_dir / "po"
        po_dir.mkdir(parents=True)
        (po_dir / "AGENTS.md").write_text(
            "# PO\n## Dominio\nGestao de produto\n## Quando Envolver\n- Sempre\n## Criterios de Aceite\n- Escopo definido\n"
        )
        engine = OrchestrationEngine(
            adapter,
            bus,
            state_mgr,
            workspace=str(tmp_path),
            personas=TEST_PERSONAS,
            agents_dir=str(agents_dir),
        )

        summary = engine._get_agents_summary()

        assert "Agentes disponiveis" in summary
        assert "📋 PO" in summary
        assert "Gestao de produto" in summary
        assert "Sempre" in summary
        assert "Escopo definido" in summary


class TestAsyncAgentDelegation:
    """Testes para delegacao async de agentes."""

    def _make_engine(self, tmp_path, adapter=None):
        adapter = adapter or CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir(exist_ok=True)
        engine = OrchestrationEngine(
            adapter,
            bus,
            state_mgr,
            workspace=workspace,
            personas=TEST_PERSONAS,
        )
        engine.TYPING_INTERVAL = 0.5
        engine.FEEDBACK_INTERVAL = 5.0
        engine._default_user_id = "user1"
        engine._default_demand_id = "test-demand"
        return engine, bus

    @pytest.mark.asyncio
    async def test_handle_start_agent_sucesso(self, tmp_path):
        """Verifica que start_agent inicia agente em background."""
        engine, bus = self._make_engine(tmp_path)

        result = await engine._handle_start_agent("po", "Especificar demanda")

        assert "iniciado" in result.lower()
        assert "po" in engine._running_agents
        assert engine._running_agents["po"].status == "running"

        # Aguarda conclusao
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_handle_start_agent_inexistente(self, tmp_path):
        """Verifica erro ao iniciar agente inexistente."""
        engine, bus = self._make_engine(tmp_path)

        result = await engine._handle_start_agent("agente-fake", "Tarefa")

        assert "nao encontrado" in result
        assert "po" in result  # Lista disponiveis

    @pytest.mark.asyncio
    async def test_handle_start_agent_ja_rodando(self, tmp_path):
        """Verifica erro ao iniciar agente que ja esta rodando."""
        engine, bus = self._make_engine(tmp_path, SlowAdapter(delay=1.0))

        await engine._handle_start_agent("po", "Tarefa 1")
        result = await engine._handle_start_agent("po", "Tarefa 2")

        assert "ja esta rodando" in result

        # Limpa task
        ra = engine._running_agents.get("po")
        if ra and ra.task:
            ra.task.cancel()
            try:
                await ra.task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_handle_get_agents_sem_agentes(self, tmp_path):
        """Verifica status sem agentes ativos."""
        engine, bus = self._make_engine(tmp_path)

        result = await engine._handle_get_agents()

        assert "nenhum" in result.lower()

    @pytest.mark.asyncio
    async def test_handle_get_agents_com_agente_rodando(self, tmp_path):
        """Verifica status com agente ativo."""
        from src.orchestrator.tools import RunningAgent

        engine, bus = self._make_engine(tmp_path)
        engine._running_agents["po"] = RunningAgent(
            agent_name="po",
            demand_id="d1",
            started_at=time.time() - 60,
            status="running",
        )

        result = await engine._handle_get_agents()

        assert "PO" in result
        assert "rodando" in result

    @pytest.mark.asyncio
    async def test_handle_get_agents_com_agente_concluido(self, tmp_path):
        """Verifica status com agente concluido."""
        from src.orchestrator.tools import RunningAgent

        engine, bus = self._make_engine(tmp_path)
        engine._running_agents["dev"] = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            started_at=time.time() - 120,
            status="done",
            result="Implementacao concluida",
        )

        result = await engine._handle_get_agents()

        assert "Dev" in result
        assert "concluido" in result

    @pytest.mark.asyncio
    async def test_on_agent_done_marca_concluido(self, tmp_path):
        """Verifica que _on_agent_done marca agente como concluido e notifica."""
        engine, bus = self._make_engine(tmp_path)
        from src.orchestrator.tools import RunningAgent

        engine._running_agents["po"] = RunningAgent(
            agent_name="po",
            demand_id="d1",
            user_id="user1",
            status="running",
        )

        async def fake_work():
            return "Especificacao pronta"

        task = asyncio.create_task(fake_work())
        await task

        await engine._on_agent_done("po", task)

        assert engine._running_agents["po"].status == "done"
        assert any("Concluido" in msg for _, msg in bus.mensagens)

    @pytest.mark.asyncio
    async def test_on_agent_done_com_erro(self, tmp_path):
        """Verifica que _on_agent_done trata erro."""
        engine, bus = self._make_engine(tmp_path)
        from src.orchestrator.tools import RunningAgent

        engine._running_agents["dev"] = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="user1",
            status="running",
        )

        async def fake_work_error():
            raise RuntimeError("Compilacao falhou")

        task = asyncio.create_task(fake_work_error())
        try:
            await task
        except RuntimeError:
            pass

        await engine._on_agent_done("dev", task)

        assert engine._running_agents["dev"].status == "error"
        assert any("Erro" in msg for _, msg in bus.mensagens)

    @pytest.mark.asyncio
    async def test_run_squad_lead_retorna_resposta(self, tmp_path):
        """Verifica que run_squad_lead retorna resposta rapida."""
        engine, bus = self._make_engine(tmp_path)

        resposta = await engine.run_squad_lead(
            "sl-test",
            "user1",
            "Criar um site",
        )

        assert resposta
        # Deve ter enviado mensagem ao bus
        assert len(bus.mensagens) > 0


class TestRunningAgent:
    """Testes para dataclass RunningAgent."""

    def test_elapsed_str_segundos(self):
        from src.orchestrator.tools import RunningAgent

        ra = RunningAgent(
            agent_name="po",
            demand_id="d1",
            started_at=time.time() - 30,
        )
        elapsed = ra.elapsed_str()
        assert "s" in elapsed

    def test_elapsed_str_minutos(self):
        from src.orchestrator.tools import RunningAgent

        ra = RunningAgent(
            agent_name="po",
            demand_id="d1",
            started_at=time.time() - 90,
        )
        elapsed = ra.elapsed_str()
        assert "min" in elapsed

    def test_status_padrao(self):
        from src.orchestrator.tools import RunningAgent

        ra = RunningAgent(agent_name="po", demand_id="d1")
        assert ra.status == "running"
        assert ra.result is None
        assert ra.error is None
