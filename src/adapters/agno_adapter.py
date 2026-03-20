"""Implementação do adapter de IA usando o framework Agno."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable

from src.adapters.interface import AIAgentAdapter
from src.adapters.mcp_tools_server import SquadMCPToolsServer
from src.adapters.prompt_builder import build_prompt
from src.models import AgentStatus

logger = logging.getLogger("ai-squad.adapter.agno")

# Número padrão de runs no histórico de contexto
_DEFAULT_HISTORY_RUNS = 5


def _normalize_model_id(model_id: str) -> str:
    """Normaliza model_id para o formato provider:model_id do Agno.

    Se já contém ':', retorna como está (passthrough).
    Senão, adiciona o prefixo correto baseado no padrão do id.
    """
    if ":" in model_id:
        return model_id
    if model_id.startswith("gemini"):
        return f"google:{model_id}"
    if model_id.startswith(("gpt-", "o1-", "o3-")):
        return f"openai:{model_id}"
    if model_id.startswith("claude"):
        return f"anthropic:{model_id}"
    return f"google:{model_id}"


def _resolve_tools(
    tools_config: list[str], working_dir: str = "", web_search_provider: str = ""
) -> list:
    """Resolve lista de nomes de toolkits para instâncias Agno."""
    tools = []

    for toolkit_name in tools_config:
        if toolkit_name == "web_search":
            provider = web_search_provider or "duckduckgo"
            if provider == "tavily":
                from agno.tools.tavily import TavilyTools

                tools.append(TavilyTools())
            elif provider == "serpapi":
                from agno.tools.serpapi import SerpApiTools

                tools.append(SerpApiTools())
            else:
                from agno.tools.duckduckgo import DuckDuckGoTools

                tools.append(DuckDuckGoTools())

        elif toolkit_name == "code_execution":
            from agno.tools.python import PythonTools

            tools.append(
                PythonTools(
                    base_dir=Path("/tmp/ai-squad-sandbox"),
                    run_code=True,
                    pip_install=False,
                )
            )

        elif toolkit_name == "shell":
            from agno.tools.shell import ShellTools

            base = Path(working_dir) if working_dir else None
            tools.append(ShellTools(base_dir=base))

        else:
            logger.warning("Toolkit desconhecido: %s (ignorando)", toolkit_name)

    return tools


class AgnoAdapter(AIAgentAdapter):
    """Adapter que executa agentes via framework Agno.

    Usa features nativas do Agno:
    - Model como string (provider:model_id)
    - Sessions com SqliteDb e session_id
    - History management com num_history_runs
    - arun() async nativo
    - Cache de agentes por nome
    - Tools geradas dinamicamente
    - Skills com fallback AGENTS.md → instruction
    """

    def __init__(
        self,
        timeout: int = 300,
        working_dir: str | None = None,
        model: str | None = None,
        allowed_tools: list[str] | None = None,
        agents_dir: str | None = None,
        global_skills_dir: str | None = None,
        state_dir: str = "",
    ) -> None:
        self._timeout = timeout
        self._working_dir = working_dir or ""
        self._model = model
        self._allowed_tools = allowed_tools or []
        self._agents_dir = agents_dir
        self._global_skills_dir = global_skills_dir
        self._state_dir = state_dir
        self._status = AgentStatus.IDLE
        self._human_needed_callback: Callable | None = None
        self._current_agent_name: str = ""

        # Cache de agentes: agent_name → (Agent, model_id)
        self._agents_cache: dict[str, tuple[Any, str]] = {}

        # DB para sessions (lazy init — só cria se state_dir fornecido)
        self._db: Any = None
        if state_dir:
            try:
                from agno.db.sqlite import SqliteDb

                db_path = Path(state_dir) / "agno_sessions.db"
                self._db = SqliteDb(db_file=str(db_path))
            except ImportError:
                logger.warning("agno.db.sqlite nao disponivel — sessions sem persistencia")

        # MCP tools server compartilhado
        self._mcp_server = SquadMCPToolsServer()

        # Tools geradas dinamicamente (cache — gera uma vez)
        self._generated_tools: list | None = None

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

    # --- Skills (Opção B: SKILL.md nativo + fallback AGENTS.md) ---

    def _get_skill_dirs(self, agent_name: str) -> list[Path]:
        """Retorna diretórios de skills nos 3 níveis."""
        dirs = []

        if agent_name and self._agents_dir:
            agent_path = Path(self._agents_dir) / agent_name
            if agent_path.exists():
                dirs.append(agent_path)

        if self._global_skills_dir:
            global_path = Path(self._global_skills_dir)
            if global_path.exists():
                dirs.append(global_path)

        if self._working_dir:
            project_skills = Path(self._working_dir) / ".claude" / "skills"
            if project_skills.exists():
                dirs.append(project_skills)

        return dirs

    def _resolve_skills(self, agent_name: str) -> tuple[Any, str]:
        """Resolve skills com fallback AGENTS.md → instruction."""
        try:
            from agno.skills import LocalSkills, Skills
        except ImportError:
            return self._resolve_skills_fallback_only(agent_name)

        loaders = []
        instruction_parts = []

        for dir_path in self._get_skill_dirs(agent_name):
            skill_md = dir_path / "SKILL.md"
            agents_md = dir_path / "AGENTS.md"

            if skill_md.exists():
                loaders.append(LocalSkills(str(dir_path)))
            elif agents_md.exists():
                try:
                    content = agents_md.read_text(encoding="utf-8")
                    if content.strip():
                        instruction_parts.append(content)
                except (OSError, UnicodeDecodeError) as e:
                    logger.warning("Erro ao ler %s: %s", agents_md, e)

        skills = Skills(loaders=loaders) if loaders else None
        instruction = "\n\n".join(instruction_parts)
        return skills, instruction

    def _resolve_skills_fallback_only(self, agent_name: str) -> tuple[None, str]:
        """Fallback quando agno.skills não está disponível."""
        instruction_parts = []
        for dir_path in self._get_skill_dirs(agent_name):
            agents_md = dir_path / "AGENTS.md"
            if agents_md.exists():
                try:
                    content = agents_md.read_text(encoding="utf-8")
                    if content.strip():
                        instruction_parts.append(content)
                except (OSError, UnicodeDecodeError):
                    pass
        return None, "\n\n".join(instruction_parts)

    # --- Tools dinâmicas ---

    def _generate_tools(self) -> list:
        """Gera function tools dinamicamente a partir das definições do MCP server."""
        if self._generated_tools is not None:
            return self._generated_tools

        server = self._mcp_server
        tools = []

        for defn in server.get_tool_definitions():
            tool_name = defn["name"]
            props = defn["inputSchema"].get("properties", {})

            # Closure captura tool_name corretamente
            async def make_tool_fn(_name: str = tool_name, **kwargs: str) -> str:
                return await server.handle_tool_call(_name, kwargs)

            make_tool_fn.__name__ = tool_name
            make_tool_fn.__qualname__ = tool_name
            make_tool_fn.__doc__ = defn["description"]
            # Type hints para o Agno gerar o schema
            make_tool_fn.__annotations__ = {p: str for p in props}
            make_tool_fn.__annotations__["return"] = str

            tools.append(make_tool_fn)

        self._generated_tools = tools
        return tools

    # --- Cache de agentes ---

    def _get_or_create_agent(
        self,
        agent_name: str,
        model_id: str,
        conversation_id: str = "",
        skills: Any = None,
        instruction: str = "",
        tools: list | None = None,
        is_override: bool = False,
    ) -> Any:
        """Retorna agente do cache ou cria novo.

        Se is_override=True, cria agente temporário sem sobrescrever cache.
        """
        from agno.agent import Agent

        # Cache hit: mesmo agente e mesmo modelo
        cached = self._agents_cache.get(agent_name)
        if cached and cached[1] == model_id and not is_override:
            return cached[0]

        # Cria novo agente
        agent_kwargs: dict[str, Any] = {
            "name": agent_name or "ai-squad-agent",
            "model": _normalize_model_id(model_id),
            "markdown": True,
            "add_history_to_context": True,
            "num_history_runs": _DEFAULT_HISTORY_RUNS,
        }

        if tools:
            agent_kwargs["tools"] = tools
        if instruction:
            agent_kwargs["instructions"] = [instruction]
        if skills:
            agent_kwargs["skills"] = skills
        if self._db:
            agent_kwargs["db"] = self._db
        if conversation_id:
            agent_kwargs["session_id"] = conversation_id

        agent = Agent(**agent_kwargs)

        # Só cacheia se não for override temporário
        if not is_override:
            self._agents_cache[agent_name] = (agent, model_id)

        return agent

    def clear_agent_cache(self) -> None:
        """Invalida cache de agentes."""
        self._agents_cache.clear()

    # --- Execução ---

    async def run(self, prompt: str, context: dict) -> str:
        """Executa agente Agno com prompt e contexto."""
        context = dict(context)
        self._status = AgentStatus.RUNNING
        agent_name = context.get("agent_name", "")
        self._current_agent_name = agent_name
        self._mcp_server.current_agent_name = agent_name

        # Model override temporário (model routing por complexidade)
        model_override = context.pop("model_override", None)
        effective_model = model_override or self._model or "gemini-2.0-flash"

        try:
            image_path = context.pop("image_path", None)
            prompt_completo = build_prompt(prompt, context)

            if image_path:
                prompt_completo = (
                    f"O usuario enviou uma imagem: {image_path}\n"
                    f"Analise o conteudo visual da imagem.\n\n"
                    f"{prompt_completo}"
                )

            conversation_id = context.get("demand_id", "")
            timeout = context.get("timeout", self._timeout)

            resultado = await self._execute_agno(
                prompt_completo,
                effective_model,
                agent_name,
                conversation_id,
                timeout,
                is_override=bool(model_override),
            )
            self._status = AgentStatus.DONE
            return resultado

        except asyncio.TimeoutError:
            self._status = AgentStatus.ERROR
            raise TimeoutError(f"Agno excedeu timeout de {self._timeout}s")
        except Exception as e:
            self._status = AgentStatus.ERROR
            raise RuntimeError(f"Erro no Agno: {e}") from e

    # Configuração de retry
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2

    async def _execute_agno(
        self,
        prompt: str,
        model_id: str,
        agent_name: str = "",
        conversation_id: str = "",
        timeout: int = 0,
        is_override: bool = False,
    ) -> str:
        """Executa agente Agno com retry e backoff exponencial."""
        effective_timeout = timeout or self._timeout
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                skills, skill_instruction = self._resolve_skills(agent_name)
                agent_tools = self._generate_tools()

                agent = self._get_or_create_agent(
                    agent_name=agent_name,
                    model_id=model_id,
                    conversation_id=conversation_id,
                    skills=skills,
                    instruction=skill_instruction,
                    tools=agent_tools if agent_tools else None,
                    is_override=is_override,
                )

                # Executa com timeout — arun() é async nativo do Agno
                async with asyncio.timeout(effective_timeout):
                    response = await agent.arun(prompt)

                if response and response.content:
                    return response.content

                return ""

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                # Context length exceeded: invalida cache (forçar novo agent com menos histórico)
                if "context_length" in error_msg or "too long" in error_msg:
                    logger.warning(
                        "[%s] Context length exceeded (tentativa %d/%d).",
                        agent_name,
                        attempt + 1,
                        self.MAX_RETRIES + 1,
                    )
                    # Remove do cache para forçar recriação
                    self._agents_cache.pop(agent_name, None)
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
        """Faz uma pergunta ao agente Agno."""
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
