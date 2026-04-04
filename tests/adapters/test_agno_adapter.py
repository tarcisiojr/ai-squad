"""Testes para o adapter Agno."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.adapters.mcp_tools_server import SquadMCPToolsServer
from ai_squad.common.events import (
    EVENT_ADVANCE_STEP,
    EVENT_GET_AGENTS,
    EVENT_GET_DEMAND_STATE,
    EVENT_GET_PIPELINE_STATE,
    EVENT_LEARN_LESSON,
    EVENT_PROGRESS,
    EVENT_READ_JOURNAL,
    EVENT_RERUN_STEP,
    EVENT_SEND_IMAGE,
    EVENT_SKIP_STEP,
    EVENT_START_AGENT,
)
from ai_squad.models import AgentStatus

# Mock de módulos agno que não estão instalados no ambiente de teste
_agno_mocks = {}
for mod_name in [
    "agno", "agno.agent", "agno.models", "agno.models.google",
    "agno.models.openai", "agno.models.anthropic", "agno.db", "agno.db.sqlite",
    "agno.tools", "agno.tools.duckduckgo", "agno.tools.tavily",
    "agno.tools.serpapi", "agno.tools.python", "agno.tools.shell",
    "agno.skills", "agno.run", "agno.run.response",
]:
    if mod_name not in sys.modules:
        _agno_mocks[mod_name] = MagicMock()

# Configura classes mock nos módulos
if "agno.tools.duckduckgo" in _agno_mocks:
    _agno_mocks["agno.tools.duckduckgo"].DuckDuckGoTools = MagicMock
if "agno.tools.tavily" in _agno_mocks:
    _agno_mocks["agno.tools.tavily"].TavilyTools = MagicMock
if "agno.tools.serpapi" in _agno_mocks:
    _agno_mocks["agno.tools.serpapi"].SerpApiTools = MagicMock
if "agno.tools.python" in _agno_mocks:
    _agno_mocks["agno.tools.python"].PythonTools = MagicMock
if "agno.tools.shell" in _agno_mocks:
    _agno_mocks["agno.tools.shell"].ShellTools = MagicMock
if "agno.skills" in _agno_mocks:
    _agno_mocks["agno.skills"].LocalSkills = MagicMock
    _agno_mocks["agno.skills"].Skills = MagicMock
if "agno.agent" in _agno_mocks:
    _agno_mocks["agno.agent"].Agent = MagicMock
if "agno.db.sqlite" in _agno_mocks:
    _agno_mocks["agno.db.sqlite"].SqliteDb = MagicMock


@pytest.fixture(autouse=True)
def _mock_agno_modules():
    """Injeta mocks do agno nos sys.modules para todos os testes."""
    with patch.dict(sys.modules, _agno_mocks):
        yield


class TestAgnoAdapterInstanciation:
    """Testes de instanciação e interface."""

    @pytest.fixture
    def adapter(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        return AgnoAdapter(timeout=30, working_dir="/tmp/test")

    def test_herda_ai_agent_adapter(self, adapter):
        assert isinstance(adapter, AIAgentAdapter)

    def test_status_inicial_idle(self, adapter):
        assert adapter.status() == AgentStatus.IDLE

    def test_timeout_configuravel(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter(timeout=600)
        assert adapter._timeout == 600

    def test_model_configuravel(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter(model="gemini-2.5-pro")
        assert adapter._model == "gemini-2.5-pro"

    def test_state_dir_cria_db(self, tmp_path):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter(state_dir=str(tmp_path))
        assert adapter._db is not None

    def test_sem_state_dir_sem_db(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter()
        assert adapter._db is None

    def test_on_human_needed(self, adapter):
        callback = AsyncMock()
        adapter.on_human_needed(callback)
        assert adapter._human_needed_callback is callback


class TestNormalizeModelId:
    """Testes para normalização de model_id."""

    def test_gemini_sem_prefixo(self):
        from ai_squad.adapters.agno_adapter import _normalize_model_id

        assert _normalize_model_id("gemini-2.0-flash") == "google:gemini-2.0-flash"

    def test_gpt_sem_prefixo(self):
        from ai_squad.adapters.agno_adapter import _normalize_model_id

        assert _normalize_model_id("gpt-4o") == "openai:gpt-4o"

    def test_claude_sem_prefixo(self):
        from ai_squad.adapters.agno_adapter import _normalize_model_id

        assert _normalize_model_id("claude-sonnet-4-20250514") == "anthropic:claude-sonnet-4-20250514"

    def test_o1_sem_prefixo(self):
        from ai_squad.adapters.agno_adapter import _normalize_model_id

        assert _normalize_model_id("o1-preview") == "openai:o1-preview"

    def test_o3_sem_prefixo(self):
        from ai_squad.adapters.agno_adapter import _normalize_model_id

        assert _normalize_model_id("o3-mini") == "openai:o3-mini"

    def test_com_prefixo_passthrough(self):
        from ai_squad.adapters.agno_adapter import _normalize_model_id

        assert _normalize_model_id("google:gemini-2.0-flash") == "google:gemini-2.0-flash"
        assert _normalize_model_id("openai:gpt-4o") == "openai:gpt-4o"
        assert _normalize_model_id("anthropic:claude-sonnet-4-20250514") == "anthropic:claude-sonnet-4-20250514"

    def test_desconhecido_fallback_google(self):
        from ai_squad.adapters.agno_adapter import _normalize_model_id

        assert _normalize_model_id("custom-model") == "google:custom-model"


class TestResolveTools:
    """Testes para resolução de toolkits."""

    def test_resolve_web_search_duckduckgo(self):
        from ai_squad.adapters.agno_adapter import _resolve_tools

        tools = _resolve_tools(["web_search"])
        assert len(tools) == 1

    def test_resolve_web_search_tavily(self):
        from ai_squad.adapters.agno_adapter import _resolve_tools

        tools = _resolve_tools(["web_search"], web_search_provider="tavily")
        assert len(tools) == 1

    def test_resolve_code_execution(self):
        from ai_squad.adapters.agno_adapter import _resolve_tools

        tools = _resolve_tools(["code_execution"])
        assert len(tools) == 1

    def test_resolve_shell(self):
        from ai_squad.adapters.agno_adapter import _resolve_tools

        tools = _resolve_tools(["shell"], working_dir="/workspace")
        assert len(tools) == 1

    def test_resolve_multiple_tools(self):
        from ai_squad.adapters.agno_adapter import _resolve_tools

        tools = _resolve_tools(["web_search", "code_execution", "shell"])
        assert len(tools) == 3

    def test_resolve_unknown_toolkit(self):
        from ai_squad.adapters.agno_adapter import _resolve_tools

        tools = _resolve_tools(["toolkit_inexistente"])
        assert len(tools) == 0

    def test_resolve_empty_list(self):
        from ai_squad.adapters.agno_adapter import _resolve_tools

        tools = _resolve_tools([])
        assert len(tools) == 0


class TestResolveSkills:
    """Testes para skills com fallback AGENTS.md."""

    @pytest.fixture
    def adapter(self, tmp_path):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        global_dir = tmp_path / "global-skills"
        global_dir.mkdir()
        working_dir = tmp_path / "workspace"
        working_dir.mkdir()

        return AgnoAdapter(
            agents_dir=str(agents_dir),
            global_skills_dir=str(global_dir),
            working_dir=str(working_dir),
        )

    def test_skill_md_nativo(self, adapter):
        agent_dir = Path(adapter._agents_dir) / "po"
        agent_dir.mkdir()
        (agent_dir / "SKILL.md").write_text("---\nname: po-skill\n---\nInstruções do PO")

        skills, instruction = adapter._resolve_skills("po")
        assert skills is not None
        assert instruction == ""

    def test_agents_md_fallback(self, adapter):
        agent_dir = Path(adapter._agents_dir) / "dev"
        agent_dir.mkdir()
        (agent_dir / "AGENTS.md").write_text("Voce e o Dev Backend.")

        skills, instruction = adapter._resolve_skills_fallback_only("dev")
        assert skills is None
        assert "Voce e o Dev Backend." in instruction

    def test_ambos_prioriza_skill_md(self, adapter):
        agent_dir = Path(adapter._agents_dir) / "qa"
        agent_dir.mkdir()
        (agent_dir / "SKILL.md").write_text("---\nname: qa-skill\n---\nQA nativo")
        (agent_dir / "AGENTS.md").write_text("QA legado")

        skills, instruction = adapter._resolve_skills("qa")
        assert skills is not None
        assert instruction == ""

    def test_diretorio_inexistente_ignorado(self, adapter):
        skills, instruction = adapter._resolve_skills_fallback_only("agente_ficticio")
        assert skills is None
        assert instruction == ""

    def test_tres_niveis_skills(self, adapter):
        agent_dir = Path(adapter._agents_dir) / "dev"
        agent_dir.mkdir()
        (agent_dir / "AGENTS.md").write_text("Agente dev")

        (Path(adapter._global_skills_dir) / "AGENTS.md").write_text("Skills globais")

        project_skills = Path(adapter._working_dir) / ".claude" / "skills"
        project_skills.mkdir(parents=True)
        (project_skills / "AGENTS.md").write_text("Skills do projeto")

        skills, instruction = adapter._resolve_skills_fallback_only("dev")
        assert "Agente dev" in instruction
        assert "Skills globais" in instruction
        assert "Skills do projeto" in instruction


class TestGenerateTools:
    """Testes para geração dinâmica de tools."""

    def test_gera_12_tools(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter()
        tools = adapter._generate_tools()
        assert len(tools) == 12

    def test_nomes_corretos(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter()
        tools = adapter._generate_tools()
        names = {t.__name__ for t in tools}
        assert "report_progress" in names
        assert "start_agent" in names
        assert "get_running_agents" in names
        assert "learn_lesson" in names
        assert "send_image" in names

    def test_cache_de_tools(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter()
        tools1 = adapter._generate_tools()
        tools2 = adapter._generate_tools()
        assert tools1 is tools2  # mesma referência (cacheado)

    @pytest.mark.asyncio
    async def test_tool_delega_para_server(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter()
        callback = AsyncMock(return_value="Agente iniciado")
        adapter._mcp_server.on(EVENT_START_AGENT, callback)

        tools = adapter._generate_tools()
        start_agent_tool = next(t for t in tools if t.__name__ == "start_agent")

        result = await start_agent_tool(agent_name="po", task_description="Especificar")
        assert result == "Agente iniciado"


class TestAgentCache:
    """Testes para cache de agentes."""

    def test_cache_miss_cria_agente(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter()
        agent = adapter._get_or_create_agent("po", "google:gemini-2.0-flash")
        assert "po" in adapter._agents_cache

    def test_cache_hit_reutiliza(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter()
        agent1 = adapter._get_or_create_agent("po", "google:gemini-2.0-flash")
        agent2 = adapter._get_or_create_agent("po", "google:gemini-2.0-flash")
        assert agent1 is agent2

    def test_model_override_nao_cacheia(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter()
        # Cria e cacheia com modelo padrão
        adapter._get_or_create_agent("po", "google:gemini-2.0-flash")
        # Override não sobrescreve
        agent_override = adapter._get_or_create_agent(
            "po", "openai:gpt-4o", is_override=True
        )
        # Cache continua com modelo original
        assert adapter._agents_cache["po"][1] == "google:gemini-2.0-flash"

    def test_clear_cache(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter()
        adapter._get_or_create_agent("po", "google:gemini-2.0-flash")
        adapter._get_or_create_agent("dev", "google:gemini-2.5-pro")
        assert len(adapter._agents_cache) == 2

        adapter.clear_agent_cache()
        assert len(adapter._agents_cache) == 0


class TestCallbacks:
    """Testes para registro de callbacks."""

    def test_all_callbacks_delegated(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter()
        callback = AsyncMock()

        adapter.on(EVENT_PROGRESS, callback)
        assert adapter._mcp_server._callbacks.has(EVENT_PROGRESS)

        adapter.on(EVENT_START_AGENT, callback)
        assert adapter._mcp_server._callbacks.has(EVENT_START_AGENT)

        adapter.on(EVENT_GET_AGENTS, callback)
        assert adapter._mcp_server._callbacks.has(EVENT_GET_AGENTS)

        adapter.on(EVENT_GET_DEMAND_STATE, callback)
        assert adapter._mcp_server._callbacks.has(EVENT_GET_DEMAND_STATE)

        adapter.on(EVENT_READ_JOURNAL, callback)
        assert adapter._mcp_server._callbacks.has(EVENT_READ_JOURNAL)

        adapter.on(EVENT_SEND_IMAGE, callback)
        assert adapter._mcp_server._callbacks.has(EVENT_SEND_IMAGE)

        adapter.on(EVENT_LEARN_LESSON, callback)
        assert adapter._mcp_server._callbacks.has(EVENT_LEARN_LESSON)

        adapter.on(EVENT_GET_PIPELINE_STATE, callback)
        assert adapter._mcp_server._callbacks.has(EVENT_GET_PIPELINE_STATE)

        adapter.on(EVENT_ADVANCE_STEP, callback)
        assert adapter._mcp_server._callbacks.has(EVENT_ADVANCE_STEP)

        adapter.on(EVENT_SKIP_STEP, callback)
        assert adapter._mcp_server._callbacks.has(EVENT_SKIP_STEP)

        adapter.on(EVENT_RERUN_STEP, callback)
        assert adapter._mcp_server._callbacks.has(EVENT_RERUN_STEP)


class TestModelOverride:
    """Testes para model override temporário."""

    @pytest.mark.asyncio
    async def test_model_override_via_context(self):
        from ai_squad.adapters.agno_adapter import AgnoAdapter

        adapter = AgnoAdapter(model="gemini-2.0-flash")

        mock_response = MagicMock()
        mock_response.content = "resultado"

        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_or_create_agent", return_value=mock_agent):
            result = await adapter.run(
                "teste",
                {"model_override": "gemini-2.5-pro", "demand_id": "test-1"},
            )

            assert result == "resultado"
            adapter._get_or_create_agent.assert_called_once()
            call_kwargs = adapter._get_or_create_agent.call_args
            assert call_kwargs.kwargs.get("is_override") is True


class TestMCPToolsServer:
    """Testes para o SquadMCPToolsServer."""

    @pytest.fixture
    def server(self):
        return SquadMCPToolsServer()

    @pytest.mark.asyncio
    async def test_report_progress(self, server):
        callback = AsyncMock()
        server.on(EVENT_PROGRESS, callback)
        server.current_agent_name = "dev"

        result = await server.handle_tool_call("report_progress", {"message": "Testando"})
        assert "Progresso" in result
        callback.assert_called_once_with("dev", "Testando")

    @pytest.mark.asyncio
    async def test_start_agent(self, server):
        callback = AsyncMock(return_value="Agente iniciado")
        server.on(EVENT_START_AGENT, callback)

        result = await server.handle_tool_call(
            "start_agent",
            {"agent_name": "po", "task_description": "Especificar demanda"},
        )
        assert result == "Agente iniciado"

    @pytest.mark.asyncio
    async def test_tool_desconhecida(self, server):
        result = await server.handle_tool_call("tool_inexistente", {})
        assert "desconhecida" in result

    @pytest.mark.asyncio
    async def test_callback_nao_configurado(self, server):
        result = await server.handle_tool_call("get_running_agents", {})
        assert "registrado" in result.lower() or "nenhum" in result.lower()

    @pytest.mark.asyncio
    async def test_learn_lesson(self, server):
        callback = AsyncMock()
        server.on(EVENT_LEARN_LESSON, callback)

        result = await server.handle_tool_call(
            "learn_lesson",
            {"category": "bug", "problem": "timeout", "solution": "aumentar timeout"},
        )
        assert "registrada" in result.lower()

    @pytest.mark.asyncio
    async def test_send_image(self, server):
        callback = AsyncMock()
        server.on(EVENT_SEND_IMAGE, callback)

        result = await server.handle_tool_call(
            "send_image",
            {"image_path": "/tmp/screenshot.png", "caption": "Teste"},
        )
        assert "enviada" in result.lower()

    def test_get_tool_definitions(self, server):
        defs = server.get_tool_definitions()
        assert len(defs) == 12
        names = {d["name"] for d in defs}
        assert "report_progress" in names
        assert "start_agent" in names
        assert "learn_lesson" in names
        assert "query_knowledge_graph" in names

    @pytest.mark.asyncio
    async def test_skip_step(self, server):
        callback = AsyncMock(return_value="Step pulado")
        server.on(EVENT_SKIP_STEP, callback)

        result = await server.handle_tool_call("skip_step", {"step_id": "revisao"})
        assert result == "Step pulado"

    @pytest.mark.asyncio
    async def test_rerun_step(self, server):
        callback = AsyncMock(return_value="Step re-executado")
        server.on(EVENT_RERUN_STEP, callback)

        result = await server.handle_tool_call("rerun_step", {"step_id": "dev"})
        assert result == "Step re-executado"

    @pytest.mark.asyncio
    async def test_advance_step(self, server):
        callback = AsyncMock(return_value="Avançado")
        server.on(EVENT_ADVANCE_STEP, callback)

        result = await server.handle_tool_call("advance_step", {})
        assert result == "Avançado"

    @pytest.mark.asyncio
    async def test_get_pipeline_state(self, server):
        callback = AsyncMock(return_value="Step 1: done, Step 2: running")
        server.on(EVENT_GET_PIPELINE_STATE, callback)

        result = await server.handle_tool_call("get_pipeline_state", {})
        assert "Step 1" in result

    @pytest.mark.asyncio
    async def test_read_journal(self, server):
        callback = AsyncMock(return_value="Decisão: avançar para dev")
        server.on(EVENT_READ_JOURNAL, callback)

        result = await server.handle_tool_call("read_journal", {})
        assert "Decisão" in result

    @pytest.mark.asyncio
    async def test_get_demand_state(self, server):
        callback = AsyncMock(return_value="Demanda ativa: criar-api")
        server.on(EVENT_GET_DEMAND_STATE, callback)

        result = await server.handle_tool_call("get_demand_state", {})
        assert "criar-api" in result


class TestPromptBuilder:
    """Testes para o prompt builder compartilhado."""

    def test_build_prompt_basico(self):
        from ai_squad.adapters.prompt_builder import build_prompt

        result = build_prompt("Ola mundo", {})
        assert result == "Ola mundo"

    def test_build_prompt_com_workspace(self):
        from ai_squad.adapters.prompt_builder import build_prompt

        context = {"workspace_context": "Projeto Python"}
        result = build_prompt("Implementar feature", context)
        assert "Contexto do Projeto" in result
        assert "Projeto Python" in result

    def test_build_prompt_com_instructions(self):
        from ai_squad.adapters.prompt_builder import build_prompt

        context = {"system_instructions": "Voce e o PO"}
        result = build_prompt("Especificar demanda", context)
        assert "Voce e o PO" in result

    def test_build_prompt_filtra_chaves_internas(self):
        from ai_squad.adapters.prompt_builder import build_prompt

        context = {
            "demand_id": "test-1",
            "agent_name": "po",
            "fase": "spec",
            "max_turns": 30,
            "custom_key": "valor_visivel",
        }
        result = build_prompt("teste", context)
        assert "demand_id" not in result
        assert "custom_key" in result

    def test_build_prompt_completo(self):
        from ai_squad.adapters.prompt_builder import build_prompt

        context = {
            "workspace_context": "Projeto X",
            "system_instructions": "Instrucoes do agente",
            "demand_id": "d-1",
            "extra": "info extra",
        }
        result = build_prompt("Meu prompt", context)
        assert "Contexto do Projeto" in result
        assert "Instrucoes do agente" in result
        assert "extra" in result
        assert "Meu prompt" in result
