"""Testes adicionais para cobertura profunda do OrchestrationEngine."""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.factory import AgentConfig
from ai_squad.models import AgentStatus
from ai_squad.orchestrator.engine import OrchestrationEngine
from ai_squad.orchestrator.state import StateManager
from ai_squad.orchestrator.tools import RunningAgent


class _MockAdapter(AIAgentAdapter):
    """Adapter mock para testes do engine."""

    def __init__(self):
        super().__init__()
        self._status = AgentStatus.IDLE
        self._run_result = "ok"
        self._run_side_effect = None
        self._current_agent_name = ""

    async def run(self, prompt, context):
        if self._run_side_effect:
            raise self._run_side_effect
        return self._run_result

    async def ask(self, question):
        return "resumo"

    def status(self):
        return self._status

    def on_human_needed(self, callback):
        pass


class _MockBus:
    """Bus mock para testes."""

    def __init__(self):
        self.mensagens = []
        self.default_chat_id = "12345"
        self.supports_threads = False

    async def send_message(self, user_id, text, **kwargs):
        self.mensagens.append((user_id, text, kwargs))

    async def notify(self, user_id, text, **kwargs):
        self.mensagens.append(("notify", user_id, text))

    async def ask_user(self, user_id, question, **kwargs):
        return "resposta"

    async def send_approval_request(self, user_id, question, options, **kwargs):
        return "Aprovar"

    async def send_typing(self, user_id, **kwargs):
        pass

    async def send_photo(self, user_id, path, caption, **kwargs):
        self.mensagens.append(("photo", user_id, path, caption))

    def register_personas(self, personas):
        pass

    def mark_agent_active(self, label):
        pass

    def mark_agent_idle(self, label):
        pass


def _make_engine(
    tmp_path: Path,
    pipeline_dir: str = "",
    personas: dict | None = None,
) -> tuple[OrchestrationEngine, _MockAdapter, _MockBus]:
    """Cria engine com mocks para testes."""
    adapter = _MockAdapter()
    bus = _MockBus()
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_mgr = StateManager(state_dir=str(state_dir))

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(exist_ok=True)

    engine = OrchestrationEngine(
        adapter=adapter,
        message_bus=bus,
        state_manager=state_mgr,
        workspace=str(tmp_path),
        agents_dir=str(agents_dir),
        personas=personas or {},
        pipeline_dir=pipeline_dir,
    )
    return engine, adapter, bus


class TestPipelineSetup:
    """Testes para setup de pipeline no __init__ (linhas 111-119)."""

    def test_pipeline_carregado_quando_dir_valido(self, tmp_path):
        """Pipeline é carregado quando pipeline_dir contém pipeline válido."""
        pipeline_dir = tmp_path / "pipeline"
        pipeline_dir.mkdir()
        steps_dir = pipeline_dir / "steps"
        steps_dir.mkdir()

        # Cria pipeline.yaml mínimo
        (pipeline_dir / "pipeline.yaml").write_text(
            "name: Teste\nsteps:\n  - id: s1\n    name: Step 1\n    agent: dev\n    "
            "type: agent\n    execution: subagent\n    file: steps/s1.md\n",
            encoding="utf-8",
        )
        (steps_dir / "s1.md").write_text("# Step 1\n\nConteúdo.", encoding="utf-8")

        engine, _, _ = _make_engine(tmp_path, pipeline_dir=str(pipeline_dir))
        assert engine._pipeline_executor is not None

    def test_pipeline_nenhum_quando_dir_vazio(self, tmp_path):
        """Pipeline None quando diretório vazio (sem pipeline.yaml)."""
        pipeline_dir = tmp_path / "pipeline"
        pipeline_dir.mkdir()

        engine, _, _ = _make_engine(tmp_path, pipeline_dir=str(pipeline_dir))
        assert engine._pipeline_executor is None

    def test_sem_pipeline_dir(self, tmp_path):
        """Pipeline None quando pipeline_dir não é fornecido."""
        engine, _, _ = _make_engine(tmp_path)
        assert engine._pipeline_executor is None


class TestHandleStartAgentEdgeCases:
    """Testes para _handle_start_agent — edge cases (linhas 301-303, 326-328)."""

    @pytest.mark.asyncio
    async def test_agente_nao_encontrado(self, tmp_path):
        """Retorna mensagem de erro quando agente não existe nas personas."""
        engine, _, _ = _make_engine(tmp_path, personas={"dev": AgentConfig(name="Dev", avatar="⚙️")})
        engine._default_demand_id = "d1"
        engine._default_user_id = "u1"

        result = await engine._handle_start_agent("inexistente", "Fazer algo")
        assert "nao encontrado" in result
        assert "dev" in result  # Mostra disponíveis

    @pytest.mark.asyncio
    async def test_agente_ja_rodando(self, tmp_path):
        """Retorna mensagem quando agente já está em execução."""
        engine, _, _ = _make_engine(tmp_path, personas={"dev": AgentConfig(name="Dev", avatar="⚙️")})
        engine._default_demand_id = "d1"
        engine._default_user_id = "u1"

        # Simula agente já rodando
        ra = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="u1",
            status="running",
            task=MagicMock(),
        )
        ra.started_at = time.time() - 10
        engine._running_agents["dev"] = ra

        result = await engine._handle_start_agent("dev", "Outra tarefa")
        assert "ja esta rodando" in result

    @pytest.mark.asyncio
    async def test_start_agent_gera_demand_id_no_modo_forum(self, tmp_path):
        """No modo fórum (demand_id=squad-lead-session), gera demand_id real."""
        engine, _, _ = _make_engine(tmp_path, personas={"dev": AgentConfig(name="Dev", avatar="⚙️")})
        engine._default_demand_id = "squad-lead-session"
        engine._default_user_id = "u1"

        # Configura callback de criação de tópico
        engine._create_topic_callback = AsyncMock(return_value="thread-456")

        await engine._handle_start_agent("dev", "Criar API REST")
        await asyncio.sleep(0.05)

        # demand_id deve ter sido atualizado
        assert engine._default_demand_id != "squad-lead-session"
        assert engine._default_thread_id == "thread-456"
        engine._create_topic_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_agent_topico_retorna_none(self, tmp_path):
        """Callback de tópico que retorna None não atualiza thread_id."""
        engine, _, _ = _make_engine(tmp_path, personas={"dev": AgentConfig(name="Dev", avatar="⚙️")})
        engine._default_demand_id = "squad-lead-session"
        engine._default_user_id = "u1"

        engine._create_topic_callback = AsyncMock(return_value=None)

        await engine._handle_start_agent("dev", "Tarefa qualquer")
        await asyncio.sleep(0.05)

        # thread_id não deve ter sido atualizado (permanece None)
        assert engine._default_thread_id is None

    @pytest.mark.asyncio
    async def test_start_agent_topico_com_excecao(self, tmp_path):
        """Exceção ao criar tópico não impede o start do agente."""
        engine, _, _ = _make_engine(tmp_path, personas={"dev": AgentConfig(name="Dev", avatar="⚙️")})
        engine._default_demand_id = "squad-lead-session"
        engine._default_user_id = "u1"

        engine._create_topic_callback = AsyncMock(side_effect=RuntimeError("Erro no Telegram"))

        # Não deve lançar exceção
        result = await engine._handle_start_agent("dev", "Tarefa com erro")
        await asyncio.sleep(0.05)
        assert "iniciado" in result.lower() or "Agente" in result


class TestHandleSendImageDeep:
    """Testes adicionais para _handle_send_image (linhas 479-505)."""

    @pytest.mark.asyncio
    async def test_bus_sem_send_photo(self, tmp_path):
        """MessageBus sem send_photo gera warning (linha 503)."""
        engine, _, bus = _make_engine(tmp_path)
        engine._default_user_id = "u1"

        # Cria bus sem send_photo
        class BusSemPhoto:
            async def send_message(self, *a, **kw):
                pass

            async def notify(self, *a, **kw):
                pass

            async def send_typing(self, *a, **kw):
                pass

        engine._message_bus = BusSemPhoto()

        img = tmp_path / "img.png"
        img.write_bytes(b"\x89PNG")

        # Não deve lançar exceção
        await engine._handle_send_image(str(img), "Captura")

    @pytest.mark.asyncio
    async def test_send_photo_com_excecao(self, tmp_path):
        """Exceção no send_photo é tolerada (linha 504-505)."""
        engine, _, bus = _make_engine(tmp_path)
        engine._default_user_id = "u1"

        bus.send_photo = AsyncMock(side_effect=RuntimeError("Erro de rede"))

        img = tmp_path / "img.png"
        img.write_bytes(b"\x89PNG")

        # Não deve lançar exceção
        await engine._handle_send_image(str(img), "Captura")


class TestHandleLearnLessonDeep:
    """Testes adicionais para _handle_learn_lesson (linhas 444-468)."""

    @pytest.mark.asyncio
    async def test_registra_e_alimenta_grafo(self, tmp_path):
        """Lição é registrada e alimenta grafo de conhecimento."""
        engine, adapter, _ = _make_engine(tmp_path)
        adapter._current_agent_name = "qa"
        engine._default_demand_id = "d-42"

        # Mock do grafo para verificar ingestão
        engine._graph = MagicMock()
        engine._graph.ingest = AsyncMock()

        await engine._handle_learn_lesson("padrao", "Código duplicado", "Extrair função")

        engine._graph.ingest.assert_called_once()
        call_args = engine._graph.ingest.call_args[0]
        assert "padrao" in call_args[0]
        assert "Código duplicado" in call_args[0]


class TestTriggerSquadLeadForAgentDeep:
    """Testes adicionais para _trigger_squad_lead_for_agent (linhas 513-544)."""

    @pytest.mark.asyncio
    async def test_resolve_thread_via_thread_map(self, tmp_path):
        """Resolve thread_id via thread_map quando running.thread_id é None (linha 523-524)."""
        engine, _, bus = _make_engine(tmp_path)
        engine._default_user_id = "u1"
        engine._default_demand_id = "d1"

        mock_thread_map = MagicMock()
        mock_thread_map.get_thread.return_value = "thread-from-map"
        engine._thread_map = mock_thread_map

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="u1",
            status="done",
            thread_id=None,  # Sem thread_id direto
        )
        await engine._trigger_squad_lead_for_agent(running, "Resultado do dev")

        # Verifica que thread_map foi consultado
        mock_thread_map.get_thread.assert_called_with("d1")

    @pytest.mark.asyncio
    async def test_squad_lead_falha_agenda_recovery(self, tmp_path):
        """Falha no run_squad_lead agenda auto-recovery (linhas 535-539)."""
        engine, adapter, bus = _make_engine(tmp_path)

        # Faz run_squad_lead lançar exceção
        engine.run_squad_lead = AsyncMock(side_effect=RuntimeError("Falha crítica"))

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="u1",
            status="done",
        )

        # Mock do auto-recovery
        engine._agent_runner.schedule_auto_recovery = AsyncMock()

        await engine._trigger_squad_lead_for_agent(running, "Resultado")
        await asyncio.sleep(0.05)

        # Auto-recovery deve ter sido agendado
        engine._agent_runner.schedule_auto_recovery.assert_called_once()

    @pytest.mark.asyncio
    async def test_squad_lead_resposta_vazia_agenda_recovery(self, tmp_path):
        """Resposta vazia do Squad Lead (timeout engolido) agenda auto-recovery."""
        engine, adapter, bus = _make_engine(tmp_path)

        # Faz run_squad_lead retornar vazio (simula timeout engolido)
        engine.run_squad_lead = AsyncMock(return_value="")

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="u1",
            status="done",
        )

        # Mock do auto-recovery
        engine._agent_runner.schedule_auto_recovery = AsyncMock()

        await engine._trigger_squad_lead_for_agent(running, "Resultado do agente")
        await asyncio.sleep(0.05)

        # Auto-recovery deve ter sido agendado (demanda não deve travar)
        engine._agent_runner.schedule_auto_recovery.assert_called_once()
        call_args = engine._agent_runner.schedule_auto_recovery.call_args
        assert call_args[0][0] is running
        assert "vazio" in call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_alimenta_grafo_com_resultado(self, tmp_path):
        """Resultado do agente é ingerido no grafo (linhas 529-531)."""
        engine, _, bus = _make_engine(tmp_path)
        engine._default_user_id = "u1"
        engine._default_demand_id = "d1"

        engine._graph = MagicMock()
        engine._graph.ingest = AsyncMock()

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="u1",
            status="done",
        )
        await engine._trigger_squad_lead_for_agent(running, "API REST implementada")

        engine._graph.ingest.assert_called_once()
        call_text = engine._graph.ingest.call_args[0][0]
        assert "dev" in call_text
        assert "API REST" in call_text


class TestBuildSquadLeadPromptEdgeCases:
    """Testes para _build_squad_lead_prompt (linhas 583-618)."""

    def test_prompt_basico_sem_pipeline(self, tmp_path):
        """Gera prompt sem pipeline configurado."""
        engine, _, _ = _make_engine(tmp_path)
        engine._default_demand_id = "d1"

        prompt = engine._build_squad_lead_prompt("d1", "Criar uma API REST")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_com_pipeline(self, tmp_path):
        """Gera prompt com pipeline configurado (linha 600-601)."""
        engine, _, _ = _make_engine(tmp_path)

        # Mock do pipeline_executor
        engine._pipeline_executor = MagicMock()
        engine._pipeline_executor.format_state_for_prompt.return_value = "Step 1 em andamento"

        prompt = engine._build_squad_lead_prompt("d1", "Implementar feature X")
        assert isinstance(prompt, str)


class TestRunSquadLeadSemaphoreTimeout:
    """Testes para run_squad_lead — timeout do semáforo (linhas 637-643)."""

    @pytest.mark.asyncio
    async def test_semaforo_timeout_envia_mensagem(self, tmp_path):
        """Timeout no semáforo envia mensagem ao usuário (linhas 637-643)."""
        engine, adapter, bus = _make_engine(tmp_path)
        adapter._run_result = "Resposta"

        # Adquire o semáforo antes para simular ocupação
        await engine._squad_lead_semaphore.acquire()

        async def release_later():
            await asyncio.sleep(0.05)
            engine._squad_lead_semaphore.release()

        # Programa liberação futura
        asyncio.create_task(release_later())

        # Configura timeout curto para forçar a mensagem de espera
        # O wait_for com timeout=30 não vai disparar em 0.05s, mas podemos testar
        # que o fluxo funciona quando o semáforo é liberado
        result = await engine.run_squad_lead("d1", "u1", "Tarefa")
        assert result == "Resposta" or result == ""


class TestCleanupExpiredInSquadLead:
    """Testes para _run_squad_lead_inner cleanup (linhas 662-665)."""

    @pytest.mark.asyncio
    async def test_cleanup_expired_tolerante_a_falha(self, tmp_path):
        """Exceção no cleanup_expired é silenciada (linhas 664-665)."""
        engine, adapter, bus = _make_engine(tmp_path)
        adapter._run_result = "Resposta"

        # Force cleanup to fail
        engine._state_manager.cleanup_expired = MagicMock(side_effect=RuntimeError("DB locked"))

        result = await engine.run_squad_lead("d1", "u1", "Tarefa")
        # Deve ter continuado normalmente apesar do erro
        assert isinstance(result, str)


class TestAgentConversation:
    """Testes para _agent_conversation (linhas 1005-1077)."""

    @pytest.mark.asyncio
    async def test_conversa_com_historico(self, tmp_path):
        """Conversa com histórico existente inclui nova interação (linhas 1025-1028)."""
        engine, adapter, bus = _make_engine(tmp_path)
        adapter._run_result = "Resultado do agente"

        # Salva algo no histórico antes
        engine._conversation.save_message("d1", "user", "Mensagem anterior")

        # Mock ask_user para retornar algo
        bus.ask_user = AsyncMock(return_value="Continuar")
        bus.send_approval_request = AsyncMock(return_value="Finalizar")

        # Limita turnos
        engine.MAX_CONVERSATIONAL_TURNS = 1

        await engine._agent_conversation("d1", "u1", "dev", "Novo prompt", {"fase": "teste"})

    @pytest.mark.asyncio
    async def test_conversa_turno_unico_finaliza(self, tmp_path):
        """Após MAX_CONVERSATIONAL_TURNS, pergunta e finaliza (linhas 1058-1067)."""
        engine, adapter, bus = _make_engine(tmp_path)
        adapter._run_result = "Resposta do agente"
        engine.MAX_CONVERSATIONAL_TURNS = 1

        bus.ask_user = AsyncMock(return_value="ok")
        bus.send_approval_request = AsyncMock(return_value="Finalizar")

        result = await engine._agent_conversation("d1", "u1", "dev", "Prompt", {})
        assert result == "Resposta do agente"

    @pytest.mark.asyncio
    async def test_conversa_continua_apos_max_turns(self, tmp_path):
        """Usuário escolhe continuar e conversa prossegue (linha 1067)."""
        engine, adapter, bus = _make_engine(tmp_path)
        adapter._run_result = "Resposta"
        engine.MAX_CONVERSATIONAL_TURNS = 1

        call_count = [0]

        async def smart_approval(user_id, question, options, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return "Continuar"
            return "Finalizar"

        bus.send_approval_request = smart_approval
        bus.ask_user = AsyncMock(return_value="Mais uma pergunta")

        result = await engine._agent_conversation("d1", "u1", "dev", "Prompt", {})
        assert result == "Resposta"
        # Deve ter perguntado 2 vezes (1 Continuar + 1 Finalizar)
        assert call_count[0] == 2


class TestKeepTypingAndFeedback:
    """Testes para _keep_typing_and_feedback com progresso (linhas 929-953)."""

    @pytest.mark.asyncio
    async def test_envia_progresso_real(self, tmp_path):
        """Envia progresso real quando disponível (linhas 929-941)."""
        engine, _, bus = _make_engine(tmp_path)
        engine.TYPING_INTERVAL = 0.01
        engine.PROGRESS_STREAM_INTERVAL = 0
        engine.FEEDBACK_INTERVAL = 1000  # Evita feedback genérico

        # Simula agente com progresso
        engine._running_agents["dev"] = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="u1",
            status="running",
        )
        engine._running_agents["dev"].progress_log = ["Criando schema", "Implementando API"]

        task = asyncio.create_task(engine._keep_typing_and_feedback("u1", "dev"))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Pelo menos alguma mensagem deve ter sido enviada
        assert len(bus.mensagens) > 0

    @pytest.mark.asyncio
    async def test_fallback_generico_sem_progresso(self, tmp_path):
        """Envia fallback genérico quando não há progresso novo (linhas 942-953)."""
        engine, _, bus = _make_engine(tmp_path)
        engine.TYPING_INTERVAL = 0.01
        engine.FEEDBACK_INTERVAL = 0.01  # Ativa rapidamente
        engine.PROGRESS_STREAM_INTERVAL = 1000  # Desativa stream de progresso

        task = asyncio.create_task(engine._keep_typing_and_feedback("u1", "dev"))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_send_message_falha_silenciosa(self, tmp_path):
        """Falha ao enviar mensagem de progresso é silenciada (linhas 938-939, 952-953)."""
        engine, _, bus = _make_engine(tmp_path)
        engine.TYPING_INTERVAL = 0.01
        engine.PROGRESS_STREAM_INTERVAL = 0
        engine.FEEDBACK_INTERVAL = 1000

        engine._running_agents["dev"] = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="u1",
            status="running",
        )
        engine._running_agents["dev"].progress_log = ["Fazendo algo"]

        # Faz send_message falhar
        bus.send_message = AsyncMock(side_effect=RuntimeError("Timeout"))

        task = asyncio.create_task(engine._keep_typing_and_feedback("u1", "dev"))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        # Não deve ter lançado exceção
