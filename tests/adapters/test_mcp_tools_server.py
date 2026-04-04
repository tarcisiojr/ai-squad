"""Testes para SquadMCPToolsServer — registro de callbacks, dispatch e definições."""

import pytest

from ai_squad.adapters.mcp_tools_server import SquadMCPToolsServer
from ai_squad.common.events import (
    EVENT_ADVANCE_STEP,
    EVENT_GET_AGENTS,
    EVENT_GET_DEMAND_STATE,
    EVENT_GET_PIPELINE_STATE,
    EVENT_LEARN_LESSON,
    EVENT_PROGRESS,
    EVENT_QUERY_GRAPH,
    EVENT_READ_JOURNAL,
    EVENT_RERUN_STEP,
    EVENT_SEND_IMAGE,
    EVENT_SKIP_STEP,
    EVENT_START_AGENT,
)


@pytest.fixture
def server() -> SquadMCPToolsServer:
    """Cria instância limpa do servidor MCP."""
    return SquadMCPToolsServer()


class TestCallbackRegistration:
    """Verifica que on() registra callbacks corretamente."""

    def test_registra_callback_unico(self, server: SquadMCPToolsServer) -> None:
        """Registrar callback com on() deve torná-lo disponível."""
        server.on(EVENT_PROGRESS, lambda *a: None)
        assert server._callbacks.has(EVENT_PROGRESS)

    def test_registra_multiplos_callbacks(self, server: SquadMCPToolsServer) -> None:
        """Registrar vários callbacks em eventos diferentes."""
        server.on(EVENT_START_AGENT, lambda *a: None)
        server.on(EVENT_GET_AGENTS, lambda *a: None)
        server.on(EVENT_READ_JOURNAL, lambda *a: None)

        assert server._callbacks.has(EVENT_START_AGENT)
        assert server._callbacks.has(EVENT_GET_AGENTS)
        assert server._callbacks.has(EVENT_READ_JOURNAL)

    def test_callback_nao_registrado_retorna_false(self, server: SquadMCPToolsServer) -> None:
        """Evento sem callback registrado deve retornar has() = False."""
        assert not server._callbacks.has(EVENT_PROGRESS)


class TestHandleToolCall:
    """Verifica que handle_tool_call despacha para o handler correto."""

    @pytest.mark.asyncio
    async def test_report_progress_com_callback(self, server: SquadMCPToolsServer) -> None:
        """report_progress deve invocar callback de progresso."""
        chamadas: list[tuple] = []

        async def cb(agent: str, msg: str) -> None:
            chamadas.append((agent, msg))

        server.on(EVENT_PROGRESS, cb)
        server.current_agent_name = "dev"

        resultado = await server.handle_tool_call("report_progress", {"message": "50% concluido"})

        assert resultado == "Progresso reportado."
        assert len(chamadas) == 1
        assert chamadas[0] == ("dev", "50% concluido")

    @pytest.mark.asyncio
    async def test_start_agent_com_callback(self, server: SquadMCPToolsServer) -> None:
        """start_agent deve invocar callback e retornar resultado."""

        async def cb(name: str, task: str) -> str:
            return f"Agente {name} iniciado"

        server.on(EVENT_START_AGENT, cb)

        resultado = await server.handle_tool_call(
            "start_agent",
            {"agent_name": "po", "task_description": "Analisar requisitos"},
        )

        assert "po" in resultado

    @pytest.mark.asyncio
    async def test_get_running_agents_sem_callback(self, server: SquadMCPToolsServer) -> None:
        """get_running_agents sem callback deve retornar mensagem padrão."""
        resultado = await server.handle_tool_call("get_running_agents", {})
        assert "Nenhum agente" in resultado

    @pytest.mark.asyncio
    async def test_get_pipeline_state_sem_callback(self, server: SquadMCPToolsServer) -> None:
        """get_pipeline_state sem callback deve retornar mensagem padrão."""
        resultado = await server.handle_tool_call("get_pipeline_state", {})
        assert "Pipeline" in resultado

    @pytest.mark.asyncio
    async def test_advance_step_com_callback(self, server: SquadMCPToolsServer) -> None:
        """advance_step deve invocar callback registrado."""

        async def cb() -> str:
            return "Avancou para step 2"

        server.on(EVENT_ADVANCE_STEP, cb)

        resultado = await server.handle_tool_call("advance_step", {})
        assert "step 2" in resultado

    @pytest.mark.asyncio
    async def test_skip_step_com_callback(self, server: SquadMCPToolsServer) -> None:
        """skip_step deve passar step_id para callback."""
        recebido: list[str] = []

        async def cb(step_id: str) -> str:
            recebido.append(step_id)
            return "Step pulado"

        server.on(EVENT_SKIP_STEP, cb)

        resultado = await server.handle_tool_call("skip_step", {"step_id": "review"})
        assert recebido == ["review"]
        assert "pulado" in resultado

    @pytest.mark.asyncio
    async def test_rerun_step_com_callback(self, server: SquadMCPToolsServer) -> None:
        """rerun_step deve passar step_id para callback."""

        async def cb(step_id: str) -> str:
            return f"Re-executando {step_id}"

        server.on(EVENT_RERUN_STEP, cb)

        resultado = await server.handle_tool_call("rerun_step", {"step_id": "dev"})
        assert "dev" in resultado

    @pytest.mark.asyncio
    async def test_read_journal_com_callback(self, server: SquadMCPToolsServer) -> None:
        """read_journal deve invocar callback e retornar conteúdo."""

        async def cb() -> str:
            return "Decisao 1: iniciar dev"

        server.on(EVENT_READ_JOURNAL, cb)

        resultado = await server.handle_tool_call("read_journal", {})
        assert "Decisao 1" in resultado

    @pytest.mark.asyncio
    async def test_send_image_com_callback(self, server: SquadMCPToolsServer) -> None:
        """send_image deve invocar callback com path e caption."""
        chamadas: list[tuple] = []

        async def cb(path: str, caption: str) -> None:
            chamadas.append((path, caption))

        server.on(EVENT_SEND_IMAGE, cb)

        resultado = await server.handle_tool_call(
            "send_image",
            {"image_path": "/tmp/img.png", "caption": "Screenshot"},
        )

        assert "Imagem enviada" in resultado
        assert chamadas[0] == ("/tmp/img.png", "Screenshot")

    @pytest.mark.asyncio
    async def test_learn_lesson_com_callback(self, server: SquadMCPToolsServer) -> None:
        """learn_lesson deve invocar callback com categoria, problema e solução."""
        chamadas: list[tuple] = []

        async def cb(cat: str, prob: str, sol: str) -> None:
            chamadas.append((cat, prob, sol))

        server.on(EVENT_LEARN_LESSON, cb)

        resultado = await server.handle_tool_call(
            "learn_lesson",
            {"category": "bug", "problem": "timeout", "solution": "aumentar limite"},
        )

        assert "Licao registrada" in resultado
        assert chamadas[0] == ("bug", "timeout", "aumentar limite")

    @pytest.mark.asyncio
    async def test_query_knowledge_graph_com_callback(self, server: SquadMCPToolsServer) -> None:
        """query_knowledge_graph deve invocar callback com query."""

        async def cb(query: str) -> str:
            return f"Resultado para: {query}"

        server.on(EVENT_QUERY_GRAPH, cb)

        resultado = await server.handle_tool_call(
            "query_knowledge_graph",
            {"query": "arquitetura"},
        )

        assert "arquitetura" in resultado

    @pytest.mark.asyncio
    async def test_get_demand_state_com_callback(self, server: SquadMCPToolsServer) -> None:
        """get_demand_state deve invocar callback registrado."""

        async def cb() -> str:
            return "Demanda d1: em andamento"

        server.on(EVENT_GET_DEMAND_STATE, cb)

        resultado = await server.handle_tool_call("get_demand_state", {})
        assert "d1" in resultado


class TestToolDesconhecida:
    """Verifica comportamento para tool inexistente."""

    @pytest.mark.asyncio
    async def test_tool_desconhecida_retorna_erro(self, server: SquadMCPToolsServer) -> None:
        """Tool inexistente deve retornar mensagem de erro."""
        resultado = await server.handle_tool_call("tool_que_nao_existe", {})
        assert "Tool desconhecida" in resultado
        assert "tool_que_nao_existe" in resultado

    @pytest.mark.asyncio
    async def test_handler_com_excecao_retorna_erro(self, server: SquadMCPToolsServer) -> None:
        """Handler que lança exceção deve retornar mensagem de erro."""

        async def cb(name: str, task: str) -> str:
            raise ValueError("Agente invalido")

        server.on(EVENT_START_AGENT, cb)

        resultado = await server.handle_tool_call(
            "start_agent",
            {"agent_name": "x", "task_description": "y"},
        )

        assert "Erro" in resultado


class TestGetToolDefinitions:
    """Verifica que get_tool_definitions retorna todas as tools."""

    def test_retorna_todas_as_tools(self, server: SquadMCPToolsServer) -> None:
        """Deve retornar definições de todas as 12 tools."""
        defs = server.get_tool_definitions()
        assert isinstance(defs, list)
        assert len(defs) == 12

    def test_cada_definicao_tem_campos_obrigatorios(self, server: SquadMCPToolsServer) -> None:
        """Cada definição deve ter name, description e inputSchema."""
        for tool_def in server.get_tool_definitions():
            assert "name" in tool_def
            assert "description" in tool_def
            assert "inputSchema" in tool_def

    def test_nomes_correspondem_aos_handlers(self, server: SquadMCPToolsServer) -> None:
        """Nomes nas definições devem corresponder aos handlers registrados."""
        nomes_defs = {d["name"] for d in server.get_tool_definitions()}
        nomes_handlers = set(server._handlers.keys())
        assert nomes_defs == nomes_handlers
