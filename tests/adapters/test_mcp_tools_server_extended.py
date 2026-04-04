"""Testes adicionais para SquadMCPToolsServer — handlers sem callback."""

import pytest

from ai_squad.adapters.mcp_tools_server import SquadMCPToolsServer
from ai_squad.common.events import (
    EVENT_ADVANCE_STEP,
    EVENT_GET_DEMAND_STATE,
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
    return SquadMCPToolsServer()


class TestHandlersSemCallback:
    """Verifica mensagens padrão quando callback não está registrado."""

    @pytest.mark.asyncio
    async def test_report_progress_sem_callback(self, server):
        """report_progress sem callback retorna mensagem padrão."""
        result = await server.handle_tool_call("report_progress", {"message": "oi"})
        assert result == "Progresso reportado."

    @pytest.mark.asyncio
    async def test_start_agent_sem_callback(self, server):
        """start_agent sem callback retorna erro."""
        result = await server.handle_tool_call(
            "start_agent", {"agent_name": "dev", "task_description": "task"}
        )
        assert "Erro" in result or "callback" in result

    @pytest.mark.asyncio
    async def test_get_demand_state_sem_callback(self, server):
        """get_demand_state sem callback retorna mensagem padrão."""
        result = await server.handle_tool_call("get_demand_state", {})
        assert "Nenhuma demanda" in result

    @pytest.mark.asyncio
    async def test_advance_step_sem_callback(self, server):
        """advance_step sem callback retorna mensagem padrão."""
        result = await server.handle_tool_call("advance_step", {})
        assert "Pipeline" in result

    @pytest.mark.asyncio
    async def test_skip_step_sem_callback(self, server):
        """skip_step sem callback retorna mensagem padrão."""
        result = await server.handle_tool_call("skip_step", {"step_id": "review"})
        assert "Pipeline" in result

    @pytest.mark.asyncio
    async def test_rerun_step_sem_callback(self, server):
        """rerun_step sem callback retorna mensagem padrão."""
        result = await server.handle_tool_call("rerun_step", {"step_id": "dev"})
        assert "Pipeline" in result

    @pytest.mark.asyncio
    async def test_read_journal_sem_callback(self, server):
        """read_journal sem callback retorna mensagem padrão."""
        result = await server.handle_tool_call("read_journal", {})
        assert "Nenhum journal" in result

    @pytest.mark.asyncio
    async def test_send_image_sem_callback(self, server):
        """send_image sem callback retorna erro."""
        result = await server.handle_tool_call(
            "send_image", {"image_path": "/tmp/img.png", "caption": "teste"}
        )
        assert "Erro" in result or "callback" in result

    @pytest.mark.asyncio
    async def test_learn_lesson_sem_callback(self, server):
        """learn_lesson sem callback retorna erro."""
        result = await server.handle_tool_call(
            "learn_lesson", {"category": "bug", "problem": "p", "solution": "s"}
        )
        assert "Erro" in result or "callback" in result

    @pytest.mark.asyncio
    async def test_query_knowledge_graph_sem_callback(self, server):
        """query_knowledge_graph sem callback retorna mensagem padrão."""
        result = await server.handle_tool_call(
            "query_knowledge_graph", {"query": "teste"}
        )
        assert "Grafo" in result or "nao configurado" in result


class TestReportProgressEdgeCases:
    """Testes de edge cases para report_progress."""

    @pytest.mark.asyncio
    async def test_report_progress_mensagem_vazia(self, server):
        """report_progress com mensagem vazia não invoca callback."""
        chamadas = []

        async def cb(agent: str, msg: str) -> None:
            chamadas.append(msg)

        server.on(EVENT_PROGRESS, cb)
        server.current_agent_name = "dev"

        result = await server.handle_tool_call("report_progress", {"message": ""})
        assert result == "Progresso reportado."
        assert len(chamadas) == 0  # Mensagem vazia não invoca callback

    @pytest.mark.asyncio
    async def test_report_progress_sem_campo_message(self, server):
        """report_progress sem campo message usa default vazio."""
        chamadas = []

        async def cb(agent: str, msg: str) -> None:
            chamadas.append(msg)

        server.on(EVENT_PROGRESS, cb)

        result = await server.handle_tool_call("report_progress", {})
        assert result == "Progresso reportado."
        assert len(chamadas) == 0


class TestStartAgentArgs:
    """Testes para verificar passagem de argumentos do start_agent."""

    @pytest.mark.asyncio
    async def test_start_agent_args_parciais(self, server):
        """start_agent com args parciais usa defaults."""
        recebido = []

        async def cb(name: str, task: str) -> str:
            recebido.append((name, task))
            return "ok"

        server.on(EVENT_START_AGENT, cb)

        await server.handle_tool_call("start_agent", {})
        assert recebido[0] == ("", "")

    @pytest.mark.asyncio
    async def test_skip_step_sem_step_id(self, server):
        """skip_step sem step_id usa default vazio."""
        recebido = []

        async def cb(step_id: str) -> str:
            recebido.append(step_id)
            return "ok"

        server.on(EVENT_SKIP_STEP, cb)

        await server.handle_tool_call("skip_step", {})
        assert recebido[0] == ""


class TestCurrentAgentName:
    """Testes para current_agent_name."""

    def test_default_vazio(self, server):
        """current_agent_name começa vazio."""
        assert server.current_agent_name == ""

    def test_atualiza_current_agent(self, server):
        """current_agent_name pode ser atualizado."""
        server.current_agent_name = "po"
        assert server.current_agent_name == "po"
