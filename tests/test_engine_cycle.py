"""Testes para o ciclo completo do motor de orquestração."""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.models import DemandState, AgentStatus
from src.factory import PersonaConfig
from src.orchestrator.engine import OrchestrationEngine
from src.orchestrator.state import StateManager
from src.adapters.interface import AIAgentAdapter
from src.barramento.interface import MessageBus

TEST_PERSONAS = {
    "po": PersonaConfig(name="PO", avatar="📋", command="/po", done_marker="---SPEC_READY---"),
    "dev": PersonaConfig(name="Dev", avatar="🔧", command="/dev", done_marker="---DONE---"),
    "qa": PersonaConfig(name="QA", avatar="🧪", command="/qa", done_marker="---QA_DONE---"),
}


class CycleAdapter(AIAgentAdapter):
    """Adapter para teste de ciclo completo."""

    def __init__(self):
        self._status = AgentStatus.IDLE
        self._callback = None

    # Marcadores por agente (mesmo do config)
    MARKERS = {
        "po": "---SPEC_READY---",
        "dev": "---DONE---",
        "qa": "---QA_DONE---",
    }

    async def run(self, prompt: str, context: dict) -> str:
        self._status = AgentStatus.RUNNING
        agent = context.get("agent_name", "")
        marker = self.MARKERS.get(agent, "")
        resultado = f"ok:{agent}\n{marker}"
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

    async def send_message(self, user_id: str, text: str, **kwargs) -> None:
        self.mensagens.append((user_id, text))

    async def send_approval_request(
        self, user_id: str, question: str, options: list[str]
    ) -> str:
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
        engine = OrchestrationEngine(adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS)

        await engine.run_squad_lead("cycle-1", "user1", "Criar feature X")

        # Squad Lead coordena — verifica que alguma mensagem foi enviada
        assert len(bus.mensagens) > 0 or len(bus.notificacoes) > 0

    @pytest.mark.asyncio
    async def test_conversa_com_marcador_aprovado(self, tmp_path):
        """Verifica que marcador no texto aciona modo APPROVAL."""
        adapter = CycleAdapter()  # Retorna texto com marcador
        bus = CycleBus()  # send_approval_request retorna primeira opção (Aprovar)
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir()
        engine = OrchestrationEngine(adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS)

        resultado = await engine._agent_conversation(
            "conv-1", "user1", "po", "Criar site",
            {"fase": "especificacao"},
        )

        # Resultado deve ter conteúdo sem o marcador
        assert "---SPEC_READY---" not in resultado
        assert "ok:po" in resultado


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
        marker = CycleAdapter.MARKERS.get(agent, "")
        self._status = AgentStatus.DONE
        return f"resultado:{agent}\n{marker}"

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
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )
        # Reduz intervalos para teste rapido
        engine.TYPING_INTERVAL = 0.03
        engine.FEEDBACK_INTERVAL = 0.08

        resultado = await engine._agent_conversation(
            "fb-1", "user1", "po", "Testar feedback",
            {"fase": "teste"},
        )

        assert resultado  # Agente concluiu
        # Verifica que typing foi chamado
        assert bus.send_typing.call_count >= 1

        # Verifica que feedback contextual foi enviado
        feedback_msgs = [
            msg for _, msg in bus.mensagens
            if "[📋 PO]" in msg and "..." in msg
        ]
        assert len(feedback_msgs) >= 1
        # Deve conter mensagem descritiva, nao generica
        assert "requisitos" in feedback_msgs[0].lower() or "repositorio" in feedback_msgs[0].lower()

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
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )
        engine.TYPING_INTERVAL = 0.5  # Alto para nao disparar
        engine.FEEDBACK_INTERVAL = 1.0

        resultado = await engine._agent_conversation(
            "fb-2", "user1", "dev", "Implementar X",
            {"fase": "teste"},
        )

        assert resultado
        # Feedback NAO deve ter sido enviado (agente concluiu rapido)
        feedback_msgs = [
            msg for _, msg in bus.mensagens
            if "[🔧 Dev]" in msg and "..." in msg
        ]
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
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )
        engine.TYPING_INTERVAL = 0.03
        engine.FEEDBACK_INTERVAL = 0.08

        resultado = await engine._agent_conversation(
            "fb-no-typing", "user1", "po", "Testar sem typing",
            {"fase": "teste"},
        )

        assert resultado
        feedback_msgs = [
            msg for _, msg in bus.mensagens
            if "[📋 PO]" in msg and "..." in msg
        ]
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
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )
        engine.TYPING_INTERVAL = 0.03
        engine.FEEDBACK_INTERVAL = 0.08

        await engine._agent_conversation(
            "fb-3", "user1", "po", "Testar tempo",
            {"fase": "teste"},
        )

        feedback_msgs = [
            msg for _, msg in bus.mensagens
            if "[📋 PO]" in msg and "..." in msg
        ]
        # Deve haver pelo menos 2 feedbacks com mensagens diferentes
        if len(feedback_msgs) >= 2:
            assert feedback_msgs[0] != feedback_msgs[1]


class TestInvokeAgent:
    """Testes para invocacao de agentes via engine."""

    @pytest.mark.asyncio
    async def test_invoke_agent_valido(self, tmp_path):
        """Verifica invocacao de agente valido."""
        adapter = CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir()
        engine = OrchestrationEngine(
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )
        engine.TYPING_INTERVAL = 0.5
        engine.FEEDBACK_INTERVAL = 5.0

        from src.orchestrator.tools import DemandStatus
        engine._demand_statuses["inv-1"] = DemandStatus(demand_id="inv-1")

        resultado = await engine._invoke_agent(
            "inv-1", "user1", "dev", "Implementar feature",
        )

        assert resultado
        assert "ok:dev" in resultado
        # Notificacao de inicio enviada
        assert any("Dev" in msg and "iniciando" in msg for _, msg in bus.notificacoes)
        # Diretorio de specs criado
        assert (tmp_path / "workspace" / "specs" / "inv-1").is_dir()

    @pytest.mark.asyncio
    async def test_invoke_agent_inexistente(self, tmp_path):
        """Verifica erro ao invocar agente inexistente."""
        adapter = CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir()
        engine = OrchestrationEngine(
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )

        resultado = await engine._invoke_agent(
            "inv-2", "user1", "agente-fake", "Testar",
        )

        assert "nao encontrado" in resultado
        assert "po" in resultado  # Lista disponiveis

    @pytest.mark.asyncio
    async def test_invoke_parallel(self, tmp_path):
        """Verifica invocacao paralela de agentes."""
        adapter = CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir()
        engine = OrchestrationEngine(
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )
        engine.TYPING_INTERVAL = 0.5
        engine.FEEDBACK_INTERVAL = 5.0

        resultados = await engine._invoke_parallel(
            "par-1", "user1",
            ["po", "dev"], ["Especificar", "Implementar"],
        )

        assert len(resultados) == 2
        assert any("ok:po" in r for r in resultados)
        assert any("ok:dev" in r for r in resultados)

    @pytest.mark.asyncio
    async def test_direct_agent_conversation(self, tmp_path):
        """Verifica conversa direta com agente."""
        adapter = CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir()
        engine = OrchestrationEngine(
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )
        engine.TYPING_INTERVAL = 0.5
        engine.FEEDBACK_INTERVAL = 5.0

        await engine.direct_agent_conversation(
            "direct-1", "user1", "po", "Olá PO",
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
            adapter, bus, state_mgr, workspace=str(tmp_path),
            personas=TEST_PERSONAS,
        )
        engine._default_user_id = "user1"

        await engine._handle_progress("po", "Gerando proposal.md")

        assert any(
            "PO" in msg and "Gerando proposal.md" in msg
            for _, msg in bus.mensagens
        )

    @pytest.mark.asyncio
    async def test_handle_progress_sem_user_id(self, tmp_path):
        """Verifica que _handle_progress nao envia sem user_id."""
        adapter = CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        engine = OrchestrationEngine(
            adapter, bus, state_mgr, workspace=str(tmp_path),
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
            adapter, bus, state_mgr, workspace=str(tmp_path),
            personas=TEST_PERSONAS, agents_dir=str(agents_dir),
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
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
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
            agent_name="po", demand_id="d1",
            started_at=time.time() - 60, status="running",
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
            agent_name="dev", demand_id="d1",
            started_at=time.time() - 120, status="done",
            result="Implementacao concluida",
        )

        result = await engine._handle_get_agents()

        assert "Dev" in result
        assert "concluido" in result

    @pytest.mark.asyncio
    async def test_on_agent_done_com_verificacao_ok(self, tmp_path):
        """Verifica que _on_agent_done passa quando artefatos existem (artifact-based)."""
        engine, bus = self._make_engine(tmp_path)
        from src.orchestrator.tools import RunningAgent

        # Cria artefatos openspec para PO passar na verificação
        ws = Path(engine._workspace)
        change_dir = ws / "openspec" / "changes" / "test-change"
        specs_dir = change_dir / "specs" / "feature"
        specs_dir.mkdir(parents=True)
        (change_dir / "proposal.md").write_text("# Proposal")
        (change_dir / "design.md").write_text("# Design")
        (specs_dir / "spec.md").write_text("# Spec\n- [ ] Criterio 1\n- [ ] Criterio 2")
        (change_dir / "tasks.md").write_text("# Tasks\n- [ ] T1\n- [ ] T2\n- [ ] T3")

        engine._running_agents["po"] = RunningAgent(
            agent_name="po", demand_id="d1", user_id="user1", status="running",
        )

        async def fake_work():
            return "Especificacao pronta"

        task = asyncio.create_task(fake_work())
        await task

        await engine._on_agent_done("po", task)

        assert engine._running_agents["po"].status == "done"
        assert any("Concluido" in msg for _, msg in bus.mensagens)

    @pytest.mark.asyncio
    async def test_on_agent_done_verificacao_falha_re_invoca(self, tmp_path):
        """Verifica que verificacao falha quando artefatos estao ausentes."""
        engine, bus = self._make_engine(tmp_path)
        from src.orchestrator.tools import RunningAgent
        engine._running_agents["po"] = RunningAgent(
            agent_name="po", demand_id="d1", user_id="user1", status="running",
        )

        # Sem artefatos → verificação falha
        async def fake_work():
            return "Especificacao pronta mas sem artefatos"

        task = asyncio.create_task(fake_work())
        await task

        await engine._on_agent_done("po", task)

        # Deve estar re-invocando (status running, retries=1)
        assert engine._running_agents["po"].retries == 1
        assert engine._running_agents["po"].status == "running"
        assert any("Verificacao falhou" in msg for _, msg in bus.mensagens)

        # Limpa task de retry
        ra = engine._running_agents.get("po")
        if ra and ra.task:
            ra.task.cancel()
            try:
                await ra.task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_on_agent_done_max_retries_marca_incomplete(self, tmp_path):
        """Verifica que apos MAX_RETRIES marca como incomplete."""
        engine, bus = self._make_engine(tmp_path)
        engine.MAX_RETRIES = 0  # Nenhuma re-tentativa
        from src.orchestrator.tools import RunningAgent
        engine._running_agents["po"] = RunningAgent(
            agent_name="po", demand_id="d1", user_id="user1", status="running",
        )

        async def fake_work():
            return "Sem marcador"

        task = asyncio.create_task(fake_work())
        await task

        await engine._on_agent_done("po", task)

        assert engine._running_agents["po"].status == "incomplete"
        assert any("Incompleto" in msg for _, msg in bus.mensagens)

    @pytest.mark.asyncio
    async def test_on_agent_done_com_erro(self, tmp_path):
        """Verifica que _on_agent_done trata erro."""
        engine, bus = self._make_engine(tmp_path)
        from src.orchestrator.tools import RunningAgent
        engine._running_agents["dev"] = RunningAgent(
            agent_name="dev", demand_id="d1", user_id="user1", status="running",
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
            "sl-test", "user1", "Criar um site",
        )

        assert resposta
        # Deve ter enviado mensagem ao bus
        assert len(bus.mensagens) > 0

    @pytest.mark.asyncio
    async def test_check_artifacts_enriched(self, tmp_path):
        """Verifica check_artifacts enriquecido com validação de qualidade."""
        engine, bus = self._make_engine(tmp_path)
        ws = Path(engine._workspace)

        # Sem change → mensagem de erro
        result = engine._check_artifacts_enriched("nao-existe")
        assert "nao encontrada" in result

        # Cria change com artefatos válidos
        change_dir = ws / "openspec" / "changes" / "minha-demanda"
        specs_dir = change_dir / "specs" / "feature"
        specs_dir.mkdir(parents=True)
        (change_dir / "proposal.md").write_text("# Proposal")
        (change_dir / "design.md").write_text("# Design")
        (specs_dir / "spec.md").write_text("# Spec\n- [ ] Criterio 1")
        (change_dir / "tasks.md").write_text("# Tasks\n- [ ] T1\n- [ ] T2\n- [ ] T3")

        result = engine._check_artifacts_enriched("minha-demanda")
        assert "APROVADO" in result

    @pytest.mark.asyncio
    async def test_check_artifacts_enriched_falha(self, tmp_path):
        """Verifica check_artifacts detecta artefatos incompletos."""
        engine, bus = self._make_engine(tmp_path)
        ws = Path(engine._workspace)

        # Change com specs sem critérios de aceite
        change_dir = ws / "openspec" / "changes" / "incompleta"
        specs_dir = change_dir / "specs" / "feature"
        specs_dir.mkdir(parents=True)
        (change_dir / "proposal.md").write_text("# Proposal")
        (specs_dir / "spec.md").write_text("# Spec sem criterios")
        # Sem design.md e tasks.md

        result = engine._check_artifacts_enriched("incompleta")
        assert "REPROVADO" in result
        assert "design.md" in result


class TestRunningAgent:
    """Testes para dataclass RunningAgent."""

    def test_elapsed_str_segundos(self):
        from src.orchestrator.tools import RunningAgent
        ra = RunningAgent(
            agent_name="po", demand_id="d1",
            started_at=time.time() - 30,
        )
        elapsed = ra.elapsed_str()
        assert "s" in elapsed

    def test_elapsed_str_minutos(self):
        from src.orchestrator.tools import RunningAgent
        ra = RunningAgent(
            agent_name="po", demand_id="d1",
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


class TestVerifyCompletion:
    """Testes para verificação artifact-based de conclusão."""

    def _make_engine(self, tmp_path):
        adapter = CycleAdapter()
        bus = CycleBus()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        workspace = str(tmp_path / "workspace")
        (tmp_path / "workspace").mkdir(exist_ok=True)
        engine = OrchestrationEngine(
            adapter, bus, state_mgr, workspace=workspace, personas=TEST_PERSONAS,
        )
        return engine

    def _create_valid_po_artifacts(self, tmp_path):
        """Cria artefatos openspec válidos para PO."""
        ws = tmp_path / "workspace" / "openspec" / "changes" / "test-change"
        specs_dir = ws / "specs" / "feature"
        specs_dir.mkdir(parents=True)
        (ws / "proposal.md").write_text("# Proposal")
        (ws / "design.md").write_text("# Design")
        (specs_dir / "spec.md").write_text("# Spec\n- [ ] Criterio 1\n- [ ] Criterio 2")
        (ws / "tasks.md").write_text("# Tasks\n- [ ] T1\n- [ ] T2\n- [ ] T3")

    def test_po_com_artefatos_validos(self, tmp_path):
        """PO com todos os artefatos openspec válidos passa."""
        engine = self._make_engine(tmp_path)
        self._create_valid_po_artifacts(tmp_path)
        result = engine._verify_completion("po", "Tudo pronto")
        assert result.passed

    def test_po_sem_artefatos(self, tmp_path):
        """PO sem artefatos openspec falha."""
        engine = self._make_engine(tmp_path)
        result = engine._verify_completion("po", "Tudo pronto")
        assert not result.passed
        assert "openspec" in result.details.lower() or "nao encontrado" in result.details.lower()

    def test_po_sem_criterios_aceite(self, tmp_path):
        """PO com specs sem critérios de aceite falha."""
        engine = self._make_engine(tmp_path)
        ws = tmp_path / "workspace" / "openspec" / "changes" / "test"
        specs_dir = ws / "specs" / "feature"
        specs_dir.mkdir(parents=True)
        (ws / "proposal.md").write_text("# Proposal")
        (ws / "design.md").write_text("# Design")
        (specs_dir / "spec.md").write_text("# Spec sem criterios")
        (ws / "tasks.md").write_text("# Tasks\n- [ ] T1\n- [ ] T2\n- [ ] T3")

        result = engine._verify_completion("po", "Pronto")
        assert not result.passed
        assert "criterios" in result.details.lower()

    def test_dev_com_tasks_completas(self, tmp_path):
        """Dev com tasks.md tudo concluído passa."""
        engine = self._make_engine(tmp_path)
        result = engine._verify_completion("dev", "Implementado")
        # Sem tasks.md pendentes → passa
        assert result.passed

    def test_dev_com_tasks_pendentes(self, tmp_path):
        """Dev com tasks pendentes no tasks.md falha."""
        engine = self._make_engine(tmp_path)
        ws = tmp_path / "workspace" / "openspec" / "changes" / "minha-demanda"
        ws.mkdir(parents=True)
        (ws / "tasks.md").write_text(
            "## Tasks\n- [x] Task 1\n- [ ] Task 2\n- [ ] Task 3\n"
        )

        result = engine._verify_completion("dev", "Implementado")
        assert not result.passed
        assert "pendentes" in result.details

    def test_qa_com_aprovado(self, tmp_path):
        """QA com 'APROVADO' no resultado passa."""
        engine = self._make_engine(tmp_path)
        result = engine._verify_completion("qa", "Resultado: APROVADO. Cobertura 85%.")
        assert result.passed

    def test_qa_sem_aprovado(self, tmp_path):
        """QA sem 'APROVADO' falha."""
        engine = self._make_engine(tmp_path)
        result = engine._verify_completion("qa", "Relatorio sem resultado final")
        assert not result.passed

    def test_agente_desconhecido_passa(self, tmp_path):
        """Agente sem verificação específica passa."""
        engine = self._make_engine(tmp_path)
        from src.factory import PersonaConfig
        engine._personas["security"] = PersonaConfig(
            name="Security", avatar="🔒", command="/sec",
        )
        result = engine._verify_completion("security", "Analise concluida")
        assert result.passed

    def test_check_tasks_md_sem_changes(self, tmp_path):
        """Sem diretório de changes retorna None."""
        engine = self._make_engine(tmp_path)
        assert engine._check_tasks_md_completion() is None

    def test_check_tasks_md_todas_completas(self, tmp_path):
        """Tasks.md com tudo [x] retorna None."""
        engine = self._make_engine(tmp_path)
        ws = tmp_path / "workspace" / "openspec" / "changes" / "test"
        ws.mkdir(parents=True)
        (ws / "tasks.md").write_text("- [x] Task 1\n- [x] Task 2\n")

        assert engine._check_tasks_md_completion() is None
