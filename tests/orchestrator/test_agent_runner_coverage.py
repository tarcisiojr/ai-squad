"""Testes adicionais para cobertura do AgentRunner — métodos não cobertos."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_squad.orchestrator.agent_runner import AgentRunner, RunnerContext, is_transient_not_timeout
from ai_squad.orchestrator.tools import RunningAgent


def _make_runner_context(tmp_path: Path) -> RunnerContext:
    """Cria RunnerContext com mocks."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    from ai_squad.orchestrator.context import WorkspaceContextCollector
    from ai_squad.orchestrator.conversation import ConversationStore
    from ai_squad.orchestrator.daily_notes import DailyNotes
    from ai_squad.orchestrator.graph import GraphStore
    from ai_squad.orchestrator.journal import JournalStore
    from ai_squad.orchestrator.lessons import LessonsStore
    from ai_squad.orchestrator.state import StateManager

    adapter = MagicMock()
    adapter.run = AsyncMock(return_value="resultado")

    bus = MagicMock()
    bus.mark_agent_active = MagicMock()
    bus.mark_agent_idle = MagicMock()
    bus.send_message = AsyncMock()

    # Agents dir com AGENTS.md
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(exist_ok=True)
    dev_dir = agents_dir / "dev"
    dev_dir.mkdir(exist_ok=True)
    (dev_dir / "AGENTS.md").write_text("# Dev Agent\nDesenvolvedor backend.")

    return RunnerContext(
        adapter=adapter,
        message_bus=bus,
        personas={"dev": MagicMock(name="Dev Backend", timeout=0, submodules=[])},
        agents_dir=agents_dir,
        workspace=str(tmp_path),
        agent_timeout=300,
        context_collector=WorkspaceContextCollector(str(tmp_path)),
        conversation=ConversationStore(str(state_dir)),
        journal=JournalStore(state_dir=str(state_dir)),
        lessons=LessonsStore(state_dir=str(state_dir)),
        daily_notes=DailyNotes(state_dir=str(state_dir)),
        state_manager=StateManager(state_dir=str(state_dir)),
        graph=GraphStore(state_dir=str(state_dir)),
    )


def _make_runner(tmp_path: Path) -> AgentRunner:
    """Cria AgentRunner com mocks."""
    ctx = _make_runner_context(tmp_path)
    on_trigger = AsyncMock()
    keep_typing = AsyncMock()

    return AgentRunner(
        ctx=ctx,
        on_squad_lead_trigger=on_trigger,
        keep_typing_callback=keep_typing,
    )


class TestAgentRunnerFormatElapsed:
    """Testes para _format_elapsed."""

    def test_segundos(self):
        """Menos de 60 segundos."""
        assert AgentRunner._format_elapsed(30) == "30s"

    def test_minutos_com_segundos(self):
        """Mais de 60 segundos com resto."""
        assert AgentRunner._format_elapsed(90) == "1min30s"

    def test_minutos_exatos(self):
        """Minutos exatos sem segundos."""
        assert AgentRunner._format_elapsed(120) == "2min"

    def test_zero_segundos(self):
        """Zero segundos."""
        assert AgentRunner._format_elapsed(0) == "0s"


class TestAgentRunnerGetAgentTimeout:
    """Testes para _get_agent_timeout."""

    def test_timeout_padrao(self, tmp_path):
        """Retorna timeout padrão quando agente não tem timeout específico."""
        runner = _make_runner(tmp_path)
        timeout = runner._get_agent_timeout("dev")
        assert timeout == 300

    def test_timeout_especifico(self, tmp_path):
        """Retorna timeout específico do agente quando configurado."""
        runner = _make_runner(tmp_path)
        persona = MagicMock()
        persona.timeout = 600
        runner._ctx.personas["dev"] = persona

        timeout = runner._get_agent_timeout("dev")
        assert timeout == 600

    def test_timeout_agente_desconhecido(self, tmp_path):
        """Retorna timeout padrão para agente não encontrado nas personas."""
        runner = _make_runner(tmp_path)
        timeout = runner._get_agent_timeout("agente-inexistente")
        assert timeout == 300


class TestAgentRunnerResolveModel:
    """Testes para _resolve_model_for_agent."""

    def test_sem_pipeline_executor(self, tmp_path):
        """Retorna None quando não há pipeline executor."""
        runner = _make_runner(tmp_path)
        result = runner._resolve_model_for_agent("dev", "d1")
        assert result is None

    def test_sem_demand_id(self, tmp_path):
        """Retorna None quando demand_id está vazio."""
        runner = _make_runner(tmp_path)
        runner._pipeline_executor = MagicMock()
        result = runner._resolve_model_for_agent("dev", "")
        assert result is None

    def test_sem_step_config(self, tmp_path):
        """Retorna None quando não há step configurado."""
        runner = _make_runner(tmp_path)
        runner._pipeline_executor = MagicMock()
        runner._pipeline_executor.get_current_step.return_value = None
        result = runner._resolve_model_for_agent("dev", "d1")
        assert result is None

    def test_agente_nao_pertence_ao_step(self, tmp_path):
        """Retorna None quando o agente não pertence ao step atual."""
        runner = _make_runner(tmp_path)
        runner._pipeline_executor = MagicMock()
        step = MagicMock()
        step.agents = ["po"]
        step.agent = "po"
        runner._pipeline_executor.get_current_step.return_value = step
        result = runner._resolve_model_for_agent("dev", "d1")
        assert result is None

    def test_resolve_modelo_para_agente_do_step(self, tmp_path):
        """Resolve modelo quando agente pertence ao step."""
        runner = _make_runner(tmp_path)
        runner._pipeline_executor = MagicMock()
        step = MagicMock()
        step.agents = ["dev"]
        step.agent = "dev"
        step.model_tier = "fast"
        runner._pipeline_executor.get_current_step.return_value = step
        runner._light_model = "haiku"
        runner._heavy_model = "sonnet"

        result = runner._resolve_model_for_agent("dev", "d1")
        assert result == "haiku"


class TestAgentRunnerConfigureModels:
    """Testes para configure_models."""

    def test_configura_modelos(self, tmp_path):
        """Configura light, heavy e default models."""
        runner = _make_runner(tmp_path)
        runner.configure_models(
            light_model="haiku",
            heavy_model="sonnet",
            default_model="claude",
        )
        assert runner._light_model == "haiku"
        assert runner._heavy_model == "sonnet"
        assert runner._default_model == "claude"


class TestAgentRunnerCircuitBreaker:
    """Testes para circuit breaker do runner."""

    def test_reset_circuit_breaker(self, tmp_path):
        """Reset limpa falhas consecutivas e fecha circuit."""
        runner = _make_runner(tmp_path)
        runner._circuit_open = True
        runner._consecutive_failures = 5

        runner.reset_circuit_breaker()
        assert runner._circuit_open is False
        assert runner._consecutive_failures == 0


class TestAgentRunnerRecordSuccess:
    """Testes para _record_agent_success."""

    def test_registra_sucesso(self, tmp_path):
        """Registra sucesso nos stores."""
        runner = _make_runner(tmp_path)
        runner._record_agent_success("dev", "d1", "30s", "Resultado do agente")

    def test_registra_sucesso_sem_demand(self, tmp_path):
        """Registra sucesso sem demand_id."""
        runner = _make_runner(tmp_path)
        runner._record_agent_success("dev", None, "30s", "Resultado")


class TestAgentRunnerRecordError:
    """Testes para _record_agent_error."""

    def test_registra_erro(self, tmp_path):
        """Registra erro nos stores."""
        runner = _make_runner(tmp_path)
        runner._record_agent_error("dev", "d1", RuntimeError("Falha"))

    def test_registra_erro_sem_demand(self, tmp_path):
        """Registra erro sem demand_id."""
        runner = _make_runner(tmp_path)
        runner._record_agent_error("dev", None, ValueError("Erro"))


class TestAgentRunnerGetStatus:
    """Testes para get_status."""

    def test_status_sem_agentes(self, tmp_path):
        """Status sem agentes retorna mensagem padrão."""
        runner = _make_runner(tmp_path)
        result = runner.get_status()
        assert "Nenhum agente ativo" in result


class TestScheduleAutoRecovery:
    """Testes para schedule_auto_recovery."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_abre_apos_threshold(self, tmp_path):
        """Circuit breaker abre após falhas consecutivas."""
        runner = _make_runner(tmp_path)
        runner._CIRCUIT_BREAKER_THRESHOLD = 2
        runner._consecutive_failures = 1
        runner._AUTO_RECOVERY_DELAY = 0  # Sem delay para testes

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="user1",
            status="error",
        )
        await runner.schedule_auto_recovery(running, "erro")
        assert runner._circuit_open is True

    @pytest.mark.asyncio
    async def test_escalacao_apos_max_recovery(self, tmp_path):
        """Escalação é disparada após max auto-recovery."""
        runner = _make_runner(tmp_path)
        runner._MAX_AUTO_RECOVERY = 0  # Escala imediatamente
        runner._AUTO_RECOVERY_DELAY = 0

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="user1",
            status="error",
        )
        await runner.schedule_auto_recovery(running, "erro persistente")


class TestEscalateToSquadLead:
    """Testes para _escalate_to_squad_lead."""

    @pytest.mark.asyncio
    async def test_escalacao_sucesso(self, tmp_path):
        """Escalação bem-sucedida dispara Squad Lead."""
        runner = _make_runner(tmp_path)
        runner._AUTO_RECOVERY_DELAY = 0

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="user1",
            status="error",
        )
        await runner._escalate_to_squad_lead(running, "erro", 2)
        # on_squad_lead_trigger deve ter sido chamado
        runner._on_squad_lead_trigger.assert_called_once()

    @pytest.mark.asyncio
    async def test_escalacao_falha_notifica_usuario(self, tmp_path):
        """Escalação que falha notifica o usuário."""
        runner = _make_runner(tmp_path)
        runner._AUTO_RECOVERY_DELAY = 0
        runner._on_squad_lead_trigger.side_effect = RuntimeError("Falha total")

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="user1",
            status="error",
        )
        await runner._escalate_to_squad_lead(running, "erro grave", 2)
        # Deve notificar o usuário
        runner._ctx.message_bus.send_message.assert_called()


class TestOnAgentDone:
    """Testes para on_agent_done."""

    @pytest.mark.asyncio
    async def test_agente_inexistente_retorna(self, tmp_path):
        """Retorna silenciosamente se agente não está registrado."""
        runner = _make_runner(tmp_path)
        task = MagicMock()
        await runner.on_agent_done("nao-existe", task)

    @pytest.mark.asyncio
    async def test_agente_concluiu_sucesso(self, tmp_path):
        """Agente que conclui com sucesso dispara Squad Lead."""
        runner = _make_runner(tmp_path)

        task = MagicMock()
        task.result.return_value = "Resultado do agente"

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="user1",
            status="running",
        )
        runner._running_agents["dev"] = running

        await runner.on_agent_done("dev", task)

        assert running.status == "done"
        runner._on_squad_lead_trigger.assert_called_once()

    @pytest.mark.asyncio
    async def test_agente_falhou_dispara_erro(self, tmp_path):
        """Agente que falha registra erro e dispara Squad Lead."""
        runner = _make_runner(tmp_path)

        task = MagicMock()
        task.result.side_effect = RuntimeError("Falha no agente")

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="user1",
            status="running",
        )
        runner._running_agents["dev"] = running

        await runner.on_agent_done("dev", task)

        assert running.status == "error"
        runner._on_squad_lead_trigger.assert_called_once()

    @pytest.mark.asyncio
    async def test_agente_timeout_mensagem_especifica(self, tmp_path):
        """Timeout gera mensagem específica."""
        runner = _make_runner(tmp_path)

        task = MagicMock()
        task.result.side_effect = asyncio.TimeoutError()

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="user1",
            status="running",
        )
        runner._running_agents["dev"] = running

        await runner.on_agent_done("dev", task)

        assert running.status == "error"
        # Verifica que o contexto menciona tempo limite
        call_args = runner._on_squad_lead_trigger.call_args
        assert "tempo limite" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_agente_com_progress_log(self, tmp_path):
        """Agente com progress log inclui resumo no contexto."""
        runner = _make_runner(tmp_path)

        task = MagicMock()
        task.result.return_value = "Resultado completo"

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="user1",
            status="running",
        )
        running.progress_log = ["Step 1 concluído", "Step 2 concluído"]
        runner._running_agents["dev"] = running

        await runner.on_agent_done("dev", task)

        call_args = runner._on_squad_lead_trigger.call_args
        assert "Progresso" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_agente_resultado_longo_truncado(self, tmp_path):
        """Resultado longo é truncado no preview."""
        runner = _make_runner(tmp_path)

        task = MagicMock()
        task.result.return_value = "x" * 3000

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="user1",
            status="running",
        )
        runner._running_agents["dev"] = running

        await runner.on_agent_done("dev", task)

        call_args = runner._on_squad_lead_trigger.call_args
        assert "..." in call_args[0][1]
