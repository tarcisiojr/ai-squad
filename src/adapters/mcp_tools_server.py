"""MCP server standalone com as tools de orquestração do AI Squad.

Expõe as 11 tools como MCP server stdio, reutilizável por qualquer adapter.
Cada tool delega para callbacks registrados pelo engine.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Callable

logger = logging.getLogger("ai-squad.mcp-server")


class SquadMCPToolsServer:
    """Servidor MCP com tools de orquestração do AI Squad.

    Encapsula callbacks do engine e os expõe como tools MCP via stdio.
    Usado pelo AgnoAdapter (e futuros adapters) para dar acesso
    às ferramentas de delegação e controle do pipeline.
    """

    def __init__(self) -> None:
        # Callbacks registrados pelo engine
        self._progress_callback: Callable | None = None
        self._start_agent_callback: Callable | None = None
        self._get_agents_callback: Callable | None = None
        self._get_demand_state_callback: Callable | None = None
        self._read_journal_callback: Callable | None = None
        self._send_image_callback: Callable | None = None
        self._learn_lesson_callback: Callable | None = None
        self._get_pipeline_state_callback: Callable | None = None
        self._advance_step_callback: Callable | None = None
        self._skip_step_callback: Callable | None = None
        self._rerun_step_callback: Callable | None = None
        self._query_graph_callback: Callable | None = None

        # Nome do agente atual (para report_progress)
        self.current_agent_name: str = ""

    # --- Registro de callbacks ---

    def set_progress_callback(self, callback: Callable) -> None:
        self._progress_callback = callback

    def set_start_agent_callback(self, callback: Callable) -> None:
        self._start_agent_callback = callback

    def set_get_agents_callback(self, callback: Callable) -> None:
        self._get_agents_callback = callback

    def set_get_demand_state_callback(self, callback: Callable) -> None:
        self._get_demand_state_callback = callback

    def set_read_journal_callback(self, callback: Callable) -> None:
        self._read_journal_callback = callback

    def set_send_image_callback(self, callback: Callable) -> None:
        self._send_image_callback = callback

    def set_learn_lesson_callback(self, callback: Callable) -> None:
        self._learn_lesson_callback = callback

    def set_get_pipeline_state_callback(self, callback: Callable) -> None:
        self._get_pipeline_state_callback = callback

    def set_advance_step_callback(self, callback: Callable) -> None:
        self._advance_step_callback = callback

    def set_skip_step_callback(self, callback: Callable) -> None:
        self._skip_step_callback = callback

    def set_rerun_step_callback(self, callback: Callable) -> None:
        self._rerun_step_callback = callback

    def set_query_graph_callback(self, callback: Callable) -> None:
        self._query_graph_callback = callback

    # --- Execução das tools ---

    async def handle_tool_call(self, tool_name: str, args: dict) -> str:
        """Executa uma tool pelo nome e retorna o resultado como string."""
        handler = self._get_handler(tool_name)
        if not handler:
            return f"Tool desconhecida: {tool_name}"
        try:
            return await handler(args)
        except Exception as e:
            logger.warning("Erro ao executar tool %s: %s", tool_name, e)
            return f"Erro: {e}"

    def _get_handler(self, tool_name: str) -> Callable | None:
        """Retorna handler para a tool especificada."""
        handlers = {
            "report_progress": self._report_progress,
            "start_agent": self._start_agent,
            "get_running_agents": self._get_running_agents,
            "get_demand_state": self._get_demand_state,
            "get_pipeline_state": self._get_pipeline_state,
            "advance_step": self._advance_step,
            "skip_step": self._skip_step,
            "rerun_step": self._rerun_step,
            "read_journal": self._read_journal,
            "send_image": self._send_image,
            "learn_lesson": self._learn_lesson,
            "query_knowledge_graph": self._query_knowledge_graph,
        }
        return handlers.get(tool_name)

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Retorna definições das tools no formato MCP."""
        return [
            {
                "name": "report_progress",
                "description": (
                    "Reporta progresso internamente ao Squad Lead. "
                    "Use para registrar etapas importantes do seu trabalho. "
                    "O Squad Lead recebe seu progresso e decide o que comunicar ao usuario."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
            },
            {
                "name": "start_agent",
                "description": ("Inicia um agente em background para executar uma tarefa."),
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
                "description": (
                    "Retorna o estado de todas as demandas ativas. "
                    "Use ANTES de decidir qualquer acao."
                ),
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_pipeline_state",
                "description": ("Retorna o estado completo do pipeline da demanda ativa."),
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
                "description": ("Registra uma licao aprendida para evitar o mesmo erro no futuro."),
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
                "description": (
                    "Consulta o grafo de conhecimento relacional. "
                    "Use para descobrir relacoes entre conceitos, padroes, "
                    "bugs e decisoes de demandas anteriores."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Termo ou conceito para buscar no grafo",
                        },
                    },
                    "required": ["query"],
                },
            },
        ]

    # --- Handlers individuais ---

    async def _report_progress(self, args: dict) -> str:
        message = args.get("message", "")
        if self._progress_callback and message:
            await self._progress_callback(self.current_agent_name, message)
        return "Progresso reportado."

    async def _start_agent(self, args: dict) -> str:
        agent_name = args.get("agent_name", "")
        task = args.get("task_description", "")
        if not self._start_agent_callback:
            return "Erro: callback nao configurado"
        return await self._start_agent_callback(agent_name, task)

    async def _get_running_agents(self, args: dict) -> str:
        if not self._get_agents_callback:
            return "Nenhum agente registrado."
        return await self._get_agents_callback()

    async def _get_demand_state(self, args: dict) -> str:
        if not self._get_demand_state_callback:
            return "Nenhuma demanda registrada."
        return await self._get_demand_state_callback()

    async def _get_pipeline_state(self, args: dict) -> str:
        if not self._get_pipeline_state_callback:
            return "Pipeline nao configurado."
        return await self._get_pipeline_state_callback()

    async def _advance_step(self, args: dict) -> str:
        if not self._advance_step_callback:
            return "Pipeline nao configurado."
        return await self._advance_step_callback()

    async def _skip_step(self, args: dict) -> str:
        step_id = args.get("step_id", "")
        if not self._skip_step_callback:
            return "Pipeline nao configurado."
        return await self._skip_step_callback(step_id)

    async def _rerun_step(self, args: dict) -> str:
        step_id = args.get("step_id", "")
        if not self._rerun_step_callback:
            return "Pipeline nao configurado."
        return await self._rerun_step_callback(step_id)

    async def _read_journal(self, args: dict) -> str:
        if not self._read_journal_callback:
            return "Nenhum journal registrado."
        return await self._read_journal_callback()

    async def _send_image(self, args: dict) -> str:
        image_path = args.get("image_path", "")
        caption = args.get("caption", "")
        if not self._send_image_callback:
            return "Erro: callback nao configurado"
        await self._send_image_callback(image_path, caption)
        return "Imagem enviada ao usuario."

    async def _query_knowledge_graph(self, args: dict) -> str:
        query = args.get("query", "")
        if not self._query_graph_callback:
            return "Grafo de conhecimento nao configurado."
        return await self._query_graph_callback(query)

    async def _learn_lesson(self, args: dict) -> str:
        category = args.get("category", "")
        problem = args.get("problem", "")
        solution = args.get("solution", "")
        if not self._learn_lesson_callback:
            return "Erro: callback nao configurado"
        await self._learn_lesson_callback(category, problem, solution)
        return "Licao registrada."


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
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                },
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
