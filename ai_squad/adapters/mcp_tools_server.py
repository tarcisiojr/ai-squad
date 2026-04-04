"""MCP server standalone com as tools de orquestração do AI Squad.

Expõe as 11 tools como MCP server stdio, reutilizável por qualquer adapter.
Cada tool delega para callbacks registrados via CallbackRegistry.
"""

import asyncio
import json
import logging
import sys
from typing import Any

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
    CallbackRegistry,
)

logger = logging.getLogger("ai-squad.mcp-server")


class SquadMCPToolsServer:
    """Servidor MCP com tools de orquestração do AI Squad.

    Encapsula callbacks do engine e os expõe como tools MCP via stdio.
    Usa CallbackRegistry para registro centralizado de callbacks.
    """

    def __init__(self) -> None:
        self._callbacks = CallbackRegistry()
        self.current_agent_name: str = ""

    def on(self, event: str, callback: Any) -> None:
        """Registra callback para um evento."""
        self._callbacks.on(event, callback)

    # --- Execução das tools ---

    async def handle_tool_call(self, tool_name: str, args: dict[str, Any]) -> str:
        """Executa uma tool pelo nome e retorna o resultado como string."""
        handler = self._handlers.get(tool_name)
        if not handler:
            return f"Tool desconhecida: {tool_name}"
        try:
            return await handler(self, args)
        except Exception as e:
            logger.warning("Erro ao executar tool %s: %s", tool_name, e)
            return f"Erro: {e}"

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Retorna definições das tools no formato MCP."""
        return _TOOL_DEFINITIONS

    # --- Handlers ---

    async def _report_progress(self, args: dict[str, Any]) -> str:
        message = args.get("message", "")
        if self._callbacks.has(EVENT_PROGRESS) and message:
            await self._callbacks.emit(EVENT_PROGRESS, self.current_agent_name, message)
        return "Progresso reportado."

    async def _start_agent(self, args: dict[str, Any]) -> str:
        if not self._callbacks.has(EVENT_START_AGENT):
            return "Erro: callback nao configurado"
        return await self._callbacks.emit(
            EVENT_START_AGENT,
            args.get("agent_name", ""),
            args.get("task_description", ""),
        )

    async def _get_running_agents(self, args: dict[str, Any]) -> str:
        if not self._callbacks.has(EVENT_GET_AGENTS):
            return "Nenhum agente registrado."
        return await self._callbacks.emit(EVENT_GET_AGENTS)

    async def _get_demand_state(self, args: dict[str, Any]) -> str:
        if not self._callbacks.has(EVENT_GET_DEMAND_STATE):
            return "Nenhuma demanda registrada."
        return await self._callbacks.emit(EVENT_GET_DEMAND_STATE)

    async def _get_pipeline_state(self, args: dict[str, Any]) -> str:
        if not self._callbacks.has(EVENT_GET_PIPELINE_STATE):
            return "Pipeline nao configurado."
        return await self._callbacks.emit(EVENT_GET_PIPELINE_STATE)

    async def _advance_step(self, args: dict[str, Any]) -> str:
        if not self._callbacks.has(EVENT_ADVANCE_STEP):
            return "Pipeline nao configurado."
        return await self._callbacks.emit(EVENT_ADVANCE_STEP)

    async def _skip_step(self, args: dict[str, Any]) -> str:
        if not self._callbacks.has(EVENT_SKIP_STEP):
            return "Pipeline nao configurado."
        return await self._callbacks.emit(EVENT_SKIP_STEP, args.get("step_id", ""))

    async def _rerun_step(self, args: dict[str, Any]) -> str:
        if not self._callbacks.has(EVENT_RERUN_STEP):
            return "Pipeline nao configurado."
        return await self._callbacks.emit(EVENT_RERUN_STEP, args.get("step_id", ""))

    async def _read_journal(self, args: dict[str, Any]) -> str:
        if not self._callbacks.has(EVENT_READ_JOURNAL):
            return "Nenhum journal registrado."
        return await self._callbacks.emit(EVENT_READ_JOURNAL)

    async def _send_image(self, args: dict[str, Any]) -> str:
        if not self._callbacks.has(EVENT_SEND_IMAGE):
            return "Erro: callback nao configurado"
        await self._callbacks.emit(
            EVENT_SEND_IMAGE,
            args.get("image_path", ""),
            args.get("caption", ""),
        )
        return "Imagem enviada ao usuario."

    async def _query_knowledge_graph(self, args: dict[str, Any]) -> str:
        if not self._callbacks.has(EVENT_QUERY_GRAPH):
            return "Grafo de conhecimento nao configurado."
        return await self._callbacks.emit(EVENT_QUERY_GRAPH, args.get("query", ""))

    async def _learn_lesson(self, args: dict[str, Any]) -> str:
        if not self._callbacks.has(EVENT_LEARN_LESSON):
            return "Erro: callback nao configurado"
        await self._callbacks.emit(
            EVENT_LEARN_LESSON,
            args.get("category", ""),
            args.get("problem", ""),
            args.get("solution", ""),
        )
        return "Licao registrada."

    # Mapeamento tool_name → handler (class-level)
    _handlers: dict[str, Any] = {
        "report_progress": _report_progress,
        "start_agent": _start_agent,
        "get_running_agents": _get_running_agents,
        "get_demand_state": _get_demand_state,
        "get_pipeline_state": _get_pipeline_state,
        "advance_step": _advance_step,
        "skip_step": _skip_step,
        "rerun_step": _rerun_step,
        "read_journal": _read_journal,
        "send_image": _send_image,
        "learn_lesson": _learn_lesson,
        "query_knowledge_graph": _query_knowledge_graph,
    }


# Definições de tools no formato MCP (constante imutável)
_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "report_progress",
        "description": "Reporta progresso internamente ao Squad Lead.",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
    {
        "name": "start_agent",
        "description": "Inicia um agente em background para executar uma tarefa.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string"},
                "task_description": {"type": "string"},
            },
            "required": ["agent_name", "task_description"],
        },
    },
    {
        "name": "get_running_agents",
        "description": "Retorna o estado de todos os agentes do time.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_demand_state",
        "description": "Retorna o estado de todas as demandas ativas.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_pipeline_state",
        "description": "Retorna o estado completo do pipeline da demanda ativa.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "advance_step",
        "description": "Avanca manualmente o pipeline para o proximo step.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "skip_step",
        "description": "Pula um step do pipeline.",
        "inputSchema": {
            "type": "object",
            "properties": {"step_id": {"type": "string"}},
            "required": ["step_id"],
        },
    },
    {
        "name": "rerun_step",
        "description": "Re-executa um step do pipeline.",
        "inputSchema": {
            "type": "object",
            "properties": {"step_id": {"type": "string"}},
            "required": ["step_id"],
        },
    },
    {
        "name": "read_journal",
        "description": "Retorna o historico de decisoes do Squad Lead.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "send_image",
        "description": "Envia uma imagem/screenshot para o usuario.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string"},
                "caption": {"type": "string"},
            },
            "required": ["image_path", "caption"],
        },
    },
    {
        "name": "learn_lesson",
        "description": "Registra uma licao aprendida para evitar o mesmo erro no futuro.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "problem": {"type": "string"},
                "solution": {"type": "string"},
            },
            "required": ["category", "problem", "solution"],
        },
    },
    {
        "name": "query_knowledge_graph",
        "description": "Consulta o grafo de conhecimento relacional.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termo para buscar no grafo"},
            },
            "required": ["query"],
        },
    },
]


# --- Modo stdio (para uso como processo MCP server) ---


async def _run_stdio_server(server: SquadMCPToolsServer) -> None:
    """Loop stdio JSON-RPC para comunicação MCP."""
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break

        try:
            request = json.loads(line.decode())
        except json.JSONDecodeError:
            continue

        method = request.get("method", "")
        req_id = request.get("id")

        response: dict[str, Any]
        if method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": server.get_tool_definitions()},
            }
        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            result_text = await server.handle_tool_call(tool_name, tool_args)
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": result_text}]},
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Metodo nao suportado: {method}"},
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    server = SquadMCPToolsServer()
    asyncio.run(_run_stdio_server(server))
