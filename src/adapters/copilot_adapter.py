"""Implementação do adapter de IA usando GitHub Copilot SDK."""

import asyncio
import logging
import os
from typing import Any, Callable

from src.adapters.interface import AIAgentAdapter
from src.adapters.mcp_tools_server import SquadMCPToolsServer
from src.adapters.prompt_builder import build_prompt
from src.models import AgentStatus

logger = logging.getLogger("ai-squad.adapter.copilot")


class CopilotAdapter(AIAgentAdapter):
    """Adapter que executa agentes via GitHub Copilot SDK.

    Usa features nativas do Copilot SDK:
    - CopilotClient com lifecycle gerenciado (start/stop)
    - Tools in-process via define_tool (sem subprocess MCP)
    - Autenticação via GITHUB_TOKEN ou copilot auth login
    """

    def __init__(
        self,
        timeout: int = 300,
        working_dir: str | None = None,
        model: str | None = None,
        allowed_tools: list[str] | None = None,
        agents_dir: str | None = None,
        global_skills_dir: str | None = None,
    ) -> None:
        self._timeout = timeout
        self._working_dir = working_dir or ""
        self._model = model
        self._allowed_tools = allowed_tools or []
        self._agents_dir = agents_dir
        self._global_skills_dir = global_skills_dir
        self._status = AgentStatus.IDLE
        self._human_needed_callback: Callable | None = None
        self._current_agent_name: str = ""

        # Client do Copilot SDK (lazy init — start() é async)
        self._client: Any = None
        self._client_started = False

        # Sessions ativas: demand_id → session
        self._sessions: dict[str, Any] = {}

        # MCP tools server compartilhado (callbacks do engine)
        self._mcp_server = SquadMCPToolsServer()

        # Tools in-process (construídas na primeira session)
        self._tools: list[Any] | None = None

    # --- Registro de callbacks (delegam para o MCP server) ---

    def set_progress_callback(self, callback: Callable) -> None:
        self._mcp_server.set_progress_callback(callback)

    def set_start_agent_callback(self, callback: Callable) -> None:
        self._mcp_server.set_start_agent_callback(callback)

    def set_get_agents_callback(self, callback: Callable) -> None:
        self._mcp_server.set_get_agents_callback(callback)

    def set_get_demand_state_callback(self, callback: Callable) -> None:
        self._mcp_server.set_get_demand_state_callback(callback)

    def set_read_journal_callback(self, callback: Callable) -> None:
        self._mcp_server.set_read_journal_callback(callback)

    def set_send_image_callback(self, callback: Callable) -> None:
        self._mcp_server.set_send_image_callback(callback)

    def set_learn_lesson_callback(self, callback: Callable) -> None:
        self._mcp_server.set_learn_lesson_callback(callback)

    def set_get_pipeline_state_callback(self, callback: Callable) -> None:
        self._mcp_server.set_get_pipeline_state_callback(callback)

    def set_advance_step_callback(self, callback: Callable) -> None:
        self._mcp_server.set_advance_step_callback(callback)

    def set_skip_step_callback(self, callback: Callable) -> None:
        self._mcp_server.set_skip_step_callback(callback)

    def set_rerun_step_callback(self, callback: Callable) -> None:
        self._mcp_server.set_rerun_step_callback(callback)

    def set_query_graph_callback(self, callback: Callable) -> None:
        self._mcp_server.set_query_graph_callback(callback)

    # --- Client lifecycle ---

    async def _ensure_client_started(self) -> None:
        """Inicializa o CopilotClient de forma lazy na primeira execução."""
        if self._client_started:
            return

        from copilot import CopilotClient

        # Auth: GITHUB_TOKEN do ambiente ou credenciais do CLI
        client_opts: dict[str, Any] = {}
        github_token = os.environ.get("GITHUB_TOKEN", "")
        if github_token and not github_token.startswith("PREENCHA_AQUI"):
            client_opts["github_token"] = github_token
            client_opts["use_logged_in_user"] = False
            logger.info("Copilot auth: usando GITHUB_TOKEN do ambiente")
        else:
            client_opts["use_logged_in_user"] = True
            logger.info("Copilot auth: usando credenciais do copilot CLI")

        self._client = CopilotClient(client_opts)
        await self._client.start()
        self._client_started = True
        logger.info("CopilotClient iniciado")

    async def shutdown(self) -> None:
        """Para o CopilotClient e libera recursos."""
        if self._client and self._client_started:
            try:
                await self._client.stop()
                logger.info("CopilotClient parado")
            except Exception as e:
                logger.warning("Erro ao parar CopilotClient: %s", e)
            finally:
                self._client_started = False
                self._sessions.clear()

    # --- Tools in-process ---

    def _build_tools(self) -> list[Any]:
        """Constroi tools in-process usando define_tool do Copilot SDK.

        Cada tool delega para o handler correspondente do SquadMCPToolsServer,
        que por sua vez chama os callbacks registrados pelo engine.
        """
        if self._tools is not None:
            return self._tools

        from copilot.tools import define_tool
        from pydantic import BaseModel, Field

        server = self._mcp_server

        # --- Modelos Pydantic para parâmetros ---

        class StartAgentParams(BaseModel):
            agent_name: str = Field(description="Nome do agente (ex: po, dev-backend)")
            task_description: str = Field(description="Descricao da tarefa para o agente")

        class ReportProgressParams(BaseModel):
            message: str = Field(description="Mensagem de progresso para o usuario")

        class SkipStepParams(BaseModel):
            step_id: str = Field(description="ID do step a pular")

        class RerunStepParams(BaseModel):
            step_id: str = Field(description="ID do step a re-executar")

        class SendImageParams(BaseModel):
            image_path: str = Field(description="Caminho da imagem")
            caption: str = Field(description="Legenda da imagem")

        class QueryGraphParams(BaseModel):
            query: str = Field(description="Termo ou conceito para buscar no grafo")

        class LearnLessonParams(BaseModel):
            category: str = Field(
                description="Categoria: bug, retrabalho, timeout, padrao, processo"
            )
            problem: str = Field(description="Descricao do problema")
            solution: str = Field(description="Solucao aplicada")

        # --- Tools ---

        @define_tool(description="Inicia um agente em background para executar uma tarefa.")
        async def start_agent(params: StartAgentParams) -> str:
            return await server.handle_tool_call(
                "start_agent",
                {"agent_name": params.agent_name, "task_description": params.task_description},
            )

        @define_tool(
            description="Reporta progresso ao usuario. Use para informar o que esta fazendo."
        )
        async def report_progress(params: ReportProgressParams) -> str:
            return await server.handle_tool_call("report_progress", {"message": params.message})

        @define_tool(description="Retorna o estado de todos os agentes do time.")
        async def get_running_agents() -> str:
            return await server.handle_tool_call("get_running_agents", {})

        @define_tool(
            description="Retorna o estado de todas as demandas ativas. Use ANTES de decidir qualquer acao."
        )
        async def get_demand_state() -> str:
            return await server.handle_tool_call("get_demand_state", {})

        @define_tool(description="Retorna o estado completo do pipeline da demanda ativa.")
        async def get_pipeline_state() -> str:
            return await server.handle_tool_call("get_pipeline_state", {})

        @define_tool(description="Avanca manualmente o pipeline para o proximo step.")
        async def advance_step() -> str:
            return await server.handle_tool_call("advance_step", {})

        @define_tool(description="Pula um step do pipeline.")
        async def skip_step(params: SkipStepParams) -> str:
            return await server.handle_tool_call("skip_step", {"step_id": params.step_id})

        @define_tool(description="Re-executa um step do pipeline.")
        async def rerun_step(params: RerunStepParams) -> str:
            return await server.handle_tool_call("rerun_step", {"step_id": params.step_id})

        @define_tool(description="Retorna o historico de decisoes do Squad Lead.")
        async def read_journal() -> str:
            return await server.handle_tool_call("read_journal", {})

        @define_tool(description="Envia uma imagem/screenshot para o usuario via Telegram.")
        async def send_image(params: SendImageParams) -> str:
            return await server.handle_tool_call(
                "send_image", {"image_path": params.image_path, "caption": params.caption}
            )

        @define_tool(description="Registra uma licao aprendida para evitar o mesmo erro no futuro.")
        async def learn_lesson(params: LearnLessonParams) -> str:
            return await server.handle_tool_call(
                "learn_lesson",
                {
                    "category": params.category,
                    "problem": params.problem,
                    "solution": params.solution,
                },
            )

        @define_tool(
            "query_knowledge_graph",
            "Consulta o grafo de conhecimento relacional. "
            "Use para descobrir relacoes entre conceitos, padroes, bugs e decisoes.",
        )
        async def query_knowledge_graph(params: QueryGraphParams) -> str:
            return await server.handle_tool_call(
                "query_knowledge_graph",
                {"query": params.query},
            )

        self._tools = [
            start_agent,
            report_progress,
            get_running_agents,
            get_demand_state,
            get_pipeline_state,
            advance_step,
            skip_step,
            rerun_step,
            read_journal,
            send_image,
            learn_lesson,
            query_knowledge_graph,
        ]
        logger.info("Tools in-process construidas: %d tools", len(self._tools))
        return self._tools

    # --- Sessions ---

    def _build_system_message(self, agent_name: str) -> str | None:
        """Monta system message a partir do AGENTS.md do agente."""
        if not agent_name or not self._agents_dir:
            return None

        from pathlib import Path

        agents_md = Path(self._agents_dir) / agent_name / "AGENTS.md"
        if agents_md.exists():
            try:
                content = agents_md.read_text(encoding="utf-8")
                if content.strip():
                    return content
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Erro ao ler %s: %s", agents_md, e)

        return None

    async def _get_or_create_session(
        self,
        demand_id: str,
        model: str,
        agent_name: str = "",
    ) -> Any:
        """Retorna session existente ou cria nova."""
        # Chave única: agente + demanda (cada agente tem sua própria session)
        # Usa "--" como separador pois o SDK rejeita ":" no session_id
        session_key = f"{agent_name}--{demand_id}" if demand_id else ""

        # Tenta retomar session em memória
        if session_key and session_key in self._sessions:
            logger.info("Retomando session em memória: %s", session_key)
            return self._sessions[session_key]

        # Cria nova session
        from copilot import PermissionHandler

        tools = self._build_tools()
        session_opts: dict[str, Any] = {
            "model": model,
            "tools": tools,
            "on_permission_request": PermissionHandler.approve_all,
        }

        # Session ID único por agente+demanda
        if session_key:
            session_opts["session_id"] = session_key

        # System message do AGENTS.md
        system_msg = self._build_system_message(agent_name)
        if system_msg:
            session_opts["system_message"] = {"content": system_msg}

        session = await self._client.create_session(session_opts)

        if session_key:
            self._sessions[session_key] = session

        logger.info(
            "Nova session criada: %s (model: %s, tools: %d)",
            demand_id or "ephemeral",
            model,
            len(tools),
        )
        return session

    # --- Execução ---

    async def run(self, prompt: str, context: dict) -> str:
        """Executa agente Copilot SDK com prompt e contexto."""
        context = dict(context)
        self._status = AgentStatus.RUNNING
        agent_name = context.get("agent_name", "")
        self._current_agent_name = agent_name
        self._mcp_server.current_agent_name = agent_name

        # Model override temporário (model routing por complexidade)
        model_override = context.pop("model_override", None)
        effective_model = model_override or self._model or "claude-sonnet-4-6"

        try:
            logger.info("[%s] Iniciando run() com model=%s", agent_name, effective_model)
            await self._ensure_client_started()

            image_path = context.pop("image_path", None)
            prompt_completo = build_prompt(prompt, context)

            if image_path:
                prompt_completo = (
                    f"O usuario enviou uma imagem: {image_path}\n"
                    f"Analise o conteudo visual da imagem.\n\n"
                    f"{prompt_completo}"
                )

            demand_id = context.get("demand_id", "")
            timeout = context.get("timeout", self._timeout)
            logger.info(
                "[%s] Chamando _execute_copilot (demand=%s, timeout=%s)",
                agent_name,
                demand_id,
                timeout,
            )

            resultado = await self._execute_copilot(
                prompt_completo,
                effective_model,
                agent_name,
                demand_id,
                timeout,
            )
            logger.info("[%s] Resposta recebida (%d chars)", agent_name, len(resultado))
            self._status = AgentStatus.DONE
            return resultado

        except asyncio.TimeoutError:
            self._status = AgentStatus.ERROR
            logger.error("[%s] Timeout no Copilot SDK (%ds)", agent_name, self._timeout)
            raise TimeoutError(f"Copilot SDK excedeu timeout de {self._timeout}s")
        except Exception as e:
            self._status = AgentStatus.ERROR
            logger.error("[%s] Erro no run(): %s", agent_name, e, exc_info=True)
            raise RuntimeError(f"Erro no Copilot SDK: {e}") from e

    # Configuração de retry
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2  # segundos (backoff: 2, 4, 8)

    async def _execute_copilot(
        self,
        prompt: str,
        model: str,
        agent_name: str = "",
        demand_id: str = "",
        timeout: int = 0,
    ) -> str:
        """Executa query via Copilot SDK com retry e backoff exponencial."""
        effective_timeout = timeout or self._timeout
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                logger.info(
                    "[%s] Tentativa %d/%d: criando session...",
                    agent_name,
                    attempt + 1,
                    self.MAX_RETRIES + 1,
                )
                session = await self._get_or_create_session(demand_id, model, agent_name)
                logger.info(
                    "[%s] Session OK, enviando prompt (%d chars)...", agent_name, len(prompt)
                )

                response = await session.send_and_wait(
                    {"prompt": prompt}, timeout=effective_timeout
                )

                logger.info("[%s] Resposta SDK recebida", agent_name)

                if response and response.data and response.data.content:
                    return response.data.content

                logger.warning("[%s] Resposta vazia do SDK", agent_name)
                return ""

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                # Session não encontrada: limpa cache e recria
                if "session not found" in error_msg or "invalid sessionid" in error_msg:
                    session_key = f"{agent_name}--{demand_id}" if demand_id else ""
                    logger.warning(
                        "[%s] Session inválida (tentativa %d/%d). Recriando...",
                        agent_name,
                        attempt + 1,
                        self.MAX_RETRIES + 1,
                    )
                    self._sessions.pop(session_key, None)
                    continue

                # Context length exceeded: limpa session e retenta
                if "context_length" in error_msg or "too long" in error_msg:
                    session_key = f"{agent_name}--{demand_id}" if demand_id else ""
                    logger.warning(
                        "[%s] Context length exceeded (tentativa %d/%d).",
                        agent_name,
                        attempt + 1,
                        self.MAX_RETRIES + 1,
                    )
                    self._sessions.pop(session_key, None)
                    continue

                # Timeout: não faz retry
                if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
                    raise

                # Outros erros: retry com backoff
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        "[%s] Erro (tentativa %d/%d): %s. Retry em %ds...",
                        agent_name,
                        attempt + 1,
                        self.MAX_RETRIES + 1,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

        raise last_error or RuntimeError("Falha apos todas as tentativas")

    async def ask(self, question: str) -> str:
        """Faz uma pergunta ao Copilot SDK."""
        return await self.run(question, {})

    def status(self) -> AgentStatus:
        """Retorna o status atual do adapter."""
        return self._status

    def on_human_needed(self, callback: Callable) -> None:
        """Registra callback para intervenção humana."""
        self._human_needed_callback = callback

    async def request_human_approval(self, question: str) -> str:
        """Solicita aprovação humana via callback registrado."""
        if self._human_needed_callback is None:
            raise RuntimeError("Nenhum callback registrado para intervencao humana")

        self._status = AgentStatus.WAITING_HUMAN
        resultado = await self._human_needed_callback(question)
        self._status = AgentStatus.RUNNING
        return resultado

    def clear_session(self, demand_id: str) -> None:
        """Remove todas as sessions de uma demanda."""
        keys_to_remove = [k for k in self._sessions if k.endswith(f"--{demand_id}")]
        for key in keys_to_remove:
            self._sessions.pop(key, None)
