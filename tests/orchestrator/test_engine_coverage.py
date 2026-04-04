"""Testes adicionais para cobertura do OrchestrationEngine — métodos não cobertos."""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.models import AgentStatus
from ai_squad.orchestrator.engine import EngineStatus, OrchestrationEngine
from ai_squad.orchestrator.state import StateManager
from ai_squad.orchestrator.tools import RunningAgent


class _MockAdapter(AIAgentAdapter):
    """Adapter mock para testes do engine."""

    def __init__(self):
        super().__init__()
        self._status = AgentStatus.IDLE
        self._run_result = "ok"
        self._run_side_effect = None

    async def run(self, prompt, context):
        if self._run_side_effect:
            raise self._run_side_effect
        return self._run_result

    async def ask(self, question):
        return "ok"

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
        pass

    def register_personas(self, personas):
        pass

    def mark_agent_active(self, label):
        pass

    def mark_agent_idle(self, label):
        pass


def _make_engine(tmp_path: Path) -> tuple[OrchestrationEngine, _MockAdapter, _MockBus]:
    """Cria engine com mocks para testes."""
    adapter = _MockAdapter()
    bus = _MockBus()
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_mgr = StateManager(state_dir=str(state_dir))

    # Cria agents dir
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(exist_ok=True)

    engine = OrchestrationEngine(
        adapter=adapter,
        message_bus=bus,
        state_manager=state_mgr,
        workspace=str(tmp_path),
        agents_dir=str(agents_dir),
    )
    return engine, adapter, bus


class TestEngineStatusMethod:
    """Testes para get_status e _get_running_agents_status."""

    def test_status_sem_atividade(self, tmp_path):
        """Status sem Squad Lead ativo nem agentes retorna mensagem padrão."""
        engine, _, _ = _make_engine(tmp_path)
        status = engine._get_running_agents_status()
        assert "Nenhum agente ativo" in status

    def test_status_com_squad_lead_ativo(self, tmp_path):
        """Status com Squad Lead processando mostra elapsed time."""
        engine, _, _ = _make_engine(tmp_path)
        engine._squad_lead_busy = True
        engine._squad_lead_busy_since = time.time() - 30

        status = engine._get_running_agents_status()
        assert "processando" in status

    def test_status_squad_lead_mais_de_um_minuto(self, tmp_path):
        """Status com Squad Lead processando há mais de 1 minuto mostra min."""
        engine, _, _ = _make_engine(tmp_path)
        engine._squad_lead_busy = True
        engine._squad_lead_busy_since = time.time() - 90

        status = engine._get_running_agents_status()
        assert "min" in status

    def test_get_status_retorna_engine_status(self, tmp_path):
        """get_status retorna EngineStatus com campos corretos."""
        engine, _, _ = _make_engine(tmp_path)
        engine._squad_lead_busy = True
        engine._squad_lead_busy_since = 12345.0
        engine._default_demand_id = "demand-abc"

        status = engine.get_status()
        assert isinstance(status, EngineStatus)
        assert status.squad_lead_busy is True
        assert status.current_demand_id == "demand-abc"


class TestHandleSendImage:
    """Testes para _handle_send_image."""

    @pytest.mark.asyncio
    async def test_envia_imagem_existente(self, tmp_path):
        """Envia imagem quando o arquivo existe."""
        engine, _, bus = _make_engine(tmp_path)
        engine._default_user_id = "user1"

        img = tmp_path / "screenshot.png"
        img.write_bytes(b"\x89PNG")

        await engine._handle_send_image(str(img), "Captura de tela")

    @pytest.mark.asyncio
    async def test_ignora_imagem_inexistente(self, tmp_path):
        """Não envia quando o arquivo não existe."""
        engine, _, bus = _make_engine(tmp_path)
        engine._default_user_id = "user1"

        await engine._handle_send_image("/nao/existe/img.png", "Captura")
        # Não deve ter mensagem de foto
        assert all("notify" != m[0] for m in bus.mensagens)

    @pytest.mark.asyncio
    async def test_ignora_sem_user_id(self, tmp_path):
        """Retorna sem enviar quando não há user_id."""
        engine, _, bus = _make_engine(tmp_path)
        engine._default_user_id = ""

        await engine._handle_send_image("/tmp/img.png", "")
        assert len(bus.mensagens) == 0

    @pytest.mark.asyncio
    async def test_resolve_caminho_relativo(self, tmp_path):
        """Caminho relativo é resolvido ao workspace."""
        engine, _, bus = _make_engine(tmp_path)
        engine._default_user_id = "user1"

        img = tmp_path / "docs" / "img.png"
        img.parent.mkdir(parents=True)
        img.write_bytes(b"\x89PNG")

        await engine._handle_send_image("docs/img.png", "Relativo")


class TestHandleLearnLesson:
    """Testes para _handle_learn_lesson."""

    @pytest.mark.asyncio
    async def test_registra_licao(self, tmp_path):
        """Registra lição aprendida com sucesso."""
        engine, adapter, _ = _make_engine(tmp_path)
        adapter._current_agent_name = "dev"
        engine._default_demand_id = "d1"

        await engine._handle_learn_lesson("bug", "timeout na API", "aumentar timeout")

    @pytest.mark.asyncio
    async def test_licao_tolerante_a_falha(self, tmp_path):
        """Falha ao registrar lição não propaga exceção."""
        engine, adapter, _ = _make_engine(tmp_path)
        adapter._current_agent_name = "dev"
        engine._default_demand_id = "d1"
        engine._lessons = MagicMock()
        engine._lessons.add.side_effect = RuntimeError("DB error")

        # Não deve lançar exceção
        await engine._handle_learn_lesson("bug", "erro", "solucao")


class TestHandleQueryGraph:
    """Testes para _handle_query_graph."""

    @pytest.mark.asyncio
    async def test_query_vazia(self, tmp_path):
        """Query vazia retorna instrução."""
        engine, _, _ = _make_engine(tmp_path)
        result = await engine._handle_query_graph("")
        assert "Informe" in result

    @pytest.mark.asyncio
    async def test_query_sem_resultado(self, tmp_path):
        """Query sem resultado retorna mensagem adequada."""
        engine, _, _ = _make_engine(tmp_path)
        result = await engine._handle_query_graph("xyzzy inexistente")
        assert "Nenhum conhecimento" in result

    @pytest.mark.asyncio
    async def test_query_com_resultado(self, tmp_path):
        """Query com resultado retorna contexto do grafo."""
        engine, _, _ = _make_engine(tmp_path)
        engine._graph = MagicMock()
        engine._graph.format_for_prompt.return_value = "Resultado: conceito X"

        result = await engine._handle_query_graph("conceito X")
        assert "conceito X" in result


class TestHandleGetDemandState:
    """Testes para callbacks de estado."""

    @pytest.mark.asyncio
    async def test_get_demand_state(self, tmp_path):
        """Retorna estado de demandas."""
        engine, _, _ = _make_engine(tmp_path)
        result = await engine._handle_get_demand_state()
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_agents(self, tmp_path):
        """Retorna status dos agentes."""
        engine, _, _ = _make_engine(tmp_path)
        result = await engine._handle_get_agents()
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_read_journal(self, tmp_path):
        """Retorna journals ativos."""
        engine, _, _ = _make_engine(tmp_path)
        result = await engine._handle_read_journal()
        assert isinstance(result, str)


class TestRunSquadLeadWithRetry:
    """Testes para _run_squad_lead_with_retry."""

    @pytest.mark.asyncio
    async def test_sucesso_na_primeira_tentativa(self, tmp_path):
        """Retorna resultado quando adapter.run() sucede."""
        engine, adapter, bus = _make_engine(tmp_path)
        adapter._run_result = "Resposta do Squad Lead"

        result = await engine._run_squad_lead_with_retry(
            "prompt", {"max_turns": 5}, "user1", None
        )
        assert result == "Resposta do Squad Lead"

    @pytest.mark.asyncio
    async def test_falha_definitiva_notifica_usuario(self, tmp_path):
        """Falha não-transiente notifica o usuário e retorna vazio."""
        engine, adapter, bus = _make_engine(tmp_path)
        adapter._run_side_effect = ValueError("Erro fatal")

        result = await engine._run_squad_lead_with_retry(
            "prompt", {"max_turns": 5}, "user1", None
        )
        assert result == ""
        # Deve ter notificado o usuário
        assert any("Erro" in str(m) for m in bus.mensagens)

    @pytest.mark.asyncio
    async def test_timeout_mostra_mensagem_especifica(self, tmp_path):
        """Timeout mostra mensagem específica ao usuário."""
        engine, adapter, bus = _make_engine(tmp_path)
        adapter._run_side_effect = asyncio.TimeoutError()

        result = await engine._run_squad_lead_with_retry(
            "prompt", {"max_turns": 5}, "user1", None
        )
        assert result == ""
        assert any("tempo limite" in str(m) for m in bus.mensagens)

    @pytest.mark.asyncio
    async def test_erro_transiente_retenta(self, tmp_path):
        """Erro transiente faz retry e eventualmente sucede."""
        engine, adapter, bus = _make_engine(tmp_path)

        call_count = [0]
        original_run = adapter.run

        async def flaky_run(prompt, context):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConnectionError("connection reset")
            return "Sucesso após retry"

        adapter.run = flaky_run

        result = await engine._run_squad_lead_with_retry(
            "prompt", {"max_turns": 5}, "user1", None
        )
        assert result == "Sucesso após retry"
        assert call_count[0] == 2


class TestTriggerSquadLead:
    """Testes para _trigger_squad_lead."""

    @pytest.mark.asyncio
    async def test_sem_user_retorna_silenciosamente(self, tmp_path):
        """Sem user_id definido, retorna sem fazer nada."""
        engine, _, bus = _make_engine(tmp_path)
        engine._default_user_id = ""
        engine._default_demand_id = ""

        await engine._trigger_squad_lead("contexto")
        assert len(bus.mensagens) == 0

    @pytest.mark.asyncio
    async def test_com_user_dispara_squad_lead(self, tmp_path):
        """Com user_id, dispara run_squad_lead."""
        engine, adapter, bus = _make_engine(tmp_path)
        engine._default_user_id = "user1"
        engine._default_demand_id = "d1"

        await engine._trigger_squad_lead("Agente concluiu")

        # Deve ter enviado mensagem (resposta do Squad Lead)
        assert len(bus.mensagens) > 0


class TestDirectAgentConversation:
    """Testes para direct_agent_conversation."""

    @pytest.mark.asyncio
    async def test_conversa_direta_basica(self, tmp_path):
        """Conversa direta com agente funciona."""
        engine, adapter, bus = _make_engine(tmp_path)
        adapter._run_result = "Resultado do agente"

        # ask_user precisa retornar algo que finalize (mock)
        bus.ask_user = AsyncMock(return_value="ok")
        bus.send_approval_request = AsyncMock(return_value="Finalizar")

        # Como é um loop, precisa limitar turnos
        engine.MAX_CONVERSATIONAL_TURNS = 1

        await engine.direct_agent_conversation("d1", "user1", "dev", "Criar API")

        # Deve ter notificado início e fim
        assert any("recebeu sua mensagem" in str(m) for m in bus.mensagens)


class TestConfigureKnowledge:
    """Testes para configure_knowledge."""

    def test_configura_knowledge_base(self, tmp_path):
        """Configure knowledge cria KnowledgeStore e ReactionTracker."""
        engine, _, _ = _make_engine(tmp_path)
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()

        engine.configure_knowledge(str(kb_dir))

        assert engine.knowledge is not None
        assert engine.reaction_tracker is not None

    def test_knowledge_none_por_padrao(self, tmp_path):
        """Knowledge é None por padrão."""
        engine, _, _ = _make_engine(tmp_path)
        assert engine.knowledge is None
        assert engine.reaction_tracker is None


class TestStopAgent:
    """Testes para stop_agent."""

    def test_para_agente_rodando(self, tmp_path):
        """Para um agente em execução."""
        engine, _, _ = _make_engine(tmp_path)
        task = MagicMock()
        engine._running_agents["dev"] = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="u1",
            status="running",
            task=task,
        )

        result = engine.stop_agent("dev")
        assert result is True
        task.cancel.assert_called_once()

    def test_nao_para_agente_inexistente(self, tmp_path):
        """Retorna False para agente inexistente."""
        engine, _, _ = _make_engine(tmp_path)
        result = engine.stop_agent("nao-existe")
        assert result is False

    def test_nao_para_agente_nao_rodando(self, tmp_path):
        """Retorna False para agente que não está rodando."""
        engine, _, _ = _make_engine(tmp_path)
        engine._running_agents["dev"] = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="u1",
            status="done",
            task=None,
        )

        result = engine.stop_agent("dev")
        assert result is False


class TestHandleStartAgent:
    """Testes para _handle_start_agent."""

    @pytest.mark.asyncio
    async def test_start_agent_basico(self, tmp_path):
        """Inicia agente e retorna mensagem de confirmação."""
        engine, _, bus = _make_engine(tmp_path)
        engine._default_demand_id = "d1"
        engine._default_user_id = "user1"

        result = await engine._handle_start_agent("dev", "Criar API")
        assert "iniciado" in result.lower() or "Agente" in result

        # Espera um pouco para a task ser criada
        await asyncio.sleep(0.05)


class TestTriggerSquadLeadForAgent:
    """Testes para _trigger_squad_lead_for_agent."""

    @pytest.mark.asyncio
    async def test_sem_user_id_retorna(self, tmp_path):
        """Retorna sem fazer nada se user_id não está disponível."""
        engine, _, bus = _make_engine(tmp_path)
        engine._default_user_id = ""

        running = RunningAgent(
            agent_name="dev",
            demand_id="",
            user_id="",
            status="done",
        )
        await engine._trigger_squad_lead_for_agent(running, "contexto")
        assert len(bus.mensagens) == 0

    @pytest.mark.asyncio
    async def test_com_user_id_dispara(self, tmp_path):
        """Dispara Squad Lead quando user_id está disponível."""
        engine, adapter, bus = _make_engine(tmp_path)
        engine._default_user_id = "user1"
        engine._default_demand_id = "d1"

        running = RunningAgent(
            agent_name="dev",
            demand_id="d1",
            user_id="user1",
            status="done",
        )
        await engine._trigger_squad_lead_for_agent(running, "Agente dev concluiu")
        # Deve ter processado (run_squad_lead chamado)
        assert len(bus.mensagens) > 0


class TestExtractAndSendImages:
    """Testes para _extract_and_send_images no engine."""

    @pytest.mark.asyncio
    async def test_texto_sem_imagens(self, tmp_path):
        """Texto sem imagens retorna o mesmo texto."""
        engine, _, _ = _make_engine(tmp_path)
        result = await engine._extract_and_send_images("user1", "Texto puro")
        assert result == "Texto puro"


class TestGetFilteredAgentsStatus:
    """Testes para get_filtered_agents_status."""

    def test_status_filtrado(self, tmp_path):
        """Retorna status filtrado por subset de agentes."""
        engine, _, _ = _make_engine(tmp_path)
        result = engine.get_filtered_agents_status({}, {})
        assert isinstance(result, str)


class TestSetThreadMap:
    """Testes para set_thread_map e set_create_topic_callback."""

    def test_set_thread_map(self, tmp_path):
        """Injeta thread_map no engine."""
        engine, _, _ = _make_engine(tmp_path)
        mock_map = MagicMock()
        engine.set_thread_map(mock_map)
        assert engine._thread_map is mock_map

    def test_set_create_topic_callback(self, tmp_path):
        """Injeta callback de criação de tópico."""
        engine, _, _ = _make_engine(tmp_path)

        async def cb(demand_id, title):
            return "thread-123"

        engine.set_create_topic_callback(cb)
        assert engine._create_topic_callback is cb
