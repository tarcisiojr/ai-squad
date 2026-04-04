"""Implementacao do adapter de IA usando Claude Agent SDK."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.adapters.prompt_builder import build_prompt
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
from ai_squad.common.retry import is_transient_error
from ai_squad.models import AgentStatus

logger = logging.getLogger("ai-squad.adapter")

# Tools MCP que precisam ser incluidas nos allowed_tools
_TOOL_NAMES = [
    "report_progress",
    "start_agent",
    "get_running_agents",
    "get_demand_state",
    "get_pipeline_state",
    "advance_step",
    "skip_step",
    "rerun_step",
    "read_journal",
    "send_image",
    "learn_lesson",
]


class ClaudeAgentSDKAdapter(AIAgentAdapter):
    """Adapter que executa Claude via Agent SDK com sessoes persistentes.

    Suporta:
    - Sessoes continuas (resume por session_id)
    - Subagentes nativos do SDK (AgentDefinition)
    - MCP tools para delegacao (start_agent, get_running_agents, etc.)
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
        super().__init__()
        self._timeout = timeout
        self._working_dir = working_dir
        self._model = model
        self._allowed_tools = allowed_tools or []
        self._agents_dir = agents_dir
        self._global_skills_dir = global_skills_dir
        self._status = AgentStatus.IDLE
        self._human_needed_callback: Callable[..., Any] | None = None
        self._sessions: dict[str, str] = {}
        self._agent_definitions: dict[str, AgentDefinition] | None = None
        self._current_agent_name: str = ""
        self._stderr_to_log: bool = True

        # MCP server com todas as tools
        self._mcp_server = self._create_mcp_server()

    # --- MCP Server ---

    def _create_mcp_server(self) -> Any:
        """Cria MCP server com tools de delegacao via callback registry."""
        adapter_ref = self

        async def _emit_tool(
            event: str, args: dict[str, Any], fallback: str = ""
        ) -> dict[str, Any]:
            """Handler genérico para tools que delegam via emit."""
            if not adapter_ref._callbacks.has(event):
                return {
                    "content": [
                        {"type": "text", "text": fallback or "Erro: callback nao configurado"}
                    ]
                }
            try:
                result = await adapter_ref.emit(event, **args)
                text = result if isinstance(result, str) else "Ok."
                return {"content": [{"type": "text", "text": text}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"Erro: {e}"}]}

        @tool(
            "report_progress",
            "Reporta progresso ao usuario. Use para informar o que esta fazendo agora. "
            "Exemplos: 'Criando proposal via openspec', 'Analisando requisitos', "
            "'Implementando task 3/7: adicionar validacao'. "
            "Chame sempre que iniciar uma etapa importante.",
            {"message": str},
        )
        async def report_progress_tool(args: dict[str, Any]) -> dict[str, Any]:
            message = args.get("message", "")
            if message and adapter_ref._callbacks.has(EVENT_PROGRESS):
                try:
                    await adapter_ref.emit(EVENT_PROGRESS, adapter_ref._current_agent_name, message)
                except Exception as e:
                    logger.warning("Erro ao enviar progresso: %s", e)
            return {"content": [{"type": "text", "text": "Progresso reportado."}]}

        @tool(
            "start_agent",
            "Inicia um agente em background para executar uma tarefa. "
            "O agente roda de forma independente e voce recebe o resultado quando ele concluir. "
            "Use para delegar trabalho ao PO, Dev, QA ou qualquer outro agente do time.",
            {"agent_name": str, "task_description": str},
        )
        async def start_agent_tool(args: dict[str, Any]) -> dict[str, Any]:
            return await _emit_tool(
                EVENT_START_AGENT,
                {
                    "agent_name": args.get("agent_name", ""),
                    "task_description": args.get("task_description", ""),
                },
            )

        @tool("get_running_agents", "Retorna o estado de todos os agentes do time.", {})
        async def get_running_agents_tool(args: dict[str, Any]) -> dict[str, Any]:
            return await _emit_tool(EVENT_GET_AGENTS, {}, "Nenhum agente registrado.")

        @tool(
            "get_demand_state",
            "Retorna o estado de todas as demandas ativas. Use ANTES de decidir qualquer acao.",
            {},
        )
        async def get_demand_state_tool(args: dict[str, Any]) -> dict[str, Any]:
            return await _emit_tool(EVENT_GET_DEMAND_STATE, {}, "Nenhuma demanda registrada.")

        @tool(
            "read_journal",
            "Retorna o historico de decisoes do Squad Lead para demandas ativas.",
            {},
        )
        async def read_journal_tool(args: dict[str, Any]) -> dict[str, Any]:
            return await _emit_tool(EVENT_READ_JOURNAL, {}, "Nenhum journal registrado.")

        @tool(
            "send_image",
            "Envia uma imagem/screenshot para o usuario via Telegram.",
            {"image_path": str, "caption": str},
        )
        async def send_image_tool(args: dict[str, Any]) -> dict[str, Any]:
            return await _emit_tool(
                EVENT_SEND_IMAGE,
                {
                    "image_path": args.get("image_path", ""),
                    "caption": args.get("caption", ""),
                },
            )

        @tool(
            "learn_lesson",
            "Registra uma licao aprendida para evitar o mesmo erro no futuro. "
            "Categorias: bug, retrabalho, timeout, padrao, processo.",
            {"category": str, "problem": str, "solution": str},
        )
        async def learn_lesson_tool(args: dict[str, Any]) -> dict[str, Any]:
            return await _emit_tool(
                EVENT_LEARN_LESSON,
                {
                    "category": args.get("category", ""),
                    "problem": args.get("problem", ""),
                    "solution": args.get("solution", ""),
                },
            )

        @tool("get_pipeline_state", "Retorna o estado completo do pipeline da demanda ativa.", {})
        async def get_pipeline_state_tool(args: dict[str, Any]) -> dict[str, Any]:
            return await _emit_tool(EVENT_GET_PIPELINE_STATE, {}, "Pipeline nao configurado.")

        @tool("advance_step", "Avanca manualmente o pipeline para o proximo step.", {})
        async def advance_step_tool(args: dict[str, Any]) -> dict[str, Any]:
            return await _emit_tool(EVENT_ADVANCE_STEP, {}, "Pipeline nao configurado.")

        @tool("skip_step", "Pula um step do pipeline.", {"step_id": str})
        async def skip_step_tool(args: dict[str, Any]) -> dict[str, Any]:
            return await _emit_tool(
                EVENT_SKIP_STEP, {"step_id": args.get("step_id", "")}, "Pipeline nao configurado."
            )

        @tool("rerun_step", "Re-executa um step do pipeline.", {"step_id": str})
        async def rerun_step_tool(args: dict[str, Any]) -> dict[str, Any]:
            return await _emit_tool(
                EVENT_RERUN_STEP, {"step_id": args.get("step_id", "")}, "Pipeline nao configurado."
            )

        return create_sdk_mcp_server(
            "ai-squad-tools",
            tools=[
                report_progress_tool,
                start_agent_tool,
                get_running_agents_tool,
                get_demand_state_tool,
                get_pipeline_state_tool,
                advance_step_tool,
                skip_step_tool,
                rerun_step_tool,
                read_journal_tool,
                send_image_tool,
                learn_lesson_tool,
            ],
        )

    # --- Configuracao ---

    @property
    def stderr_to_log(self) -> bool:
        """Se stderr do subprocess deve ser redirecionado para log."""
        return self._stderr_to_log

    @stderr_to_log.setter
    def stderr_to_log(self, value: bool) -> None:
        self._stderr_to_log = value

    def set_agent_definitions(self, agents: dict[str, AgentDefinition]) -> None:
        """Define subagentes disponiveis para o Squad Lead."""
        self._agent_definitions = agents

    # --- Execucao ---

    async def run(self, prompt: str, context: dict[str, Any]) -> str:
        """Executa Claude Agent SDK com prompt e contexto."""
        context = dict(context)
        self._status = AgentStatus.RUNNING
        agent_name = context.get("agent_name", "")
        # Mantém para compatibilidade com report_progress
        self._current_agent_name = agent_name

        # Model override temporário (model routing por complexidade)
        model_override = context.pop("model_override", None)
        original_model = self._model
        if model_override:
            self._model = model_override

        try:
            # Extrai imagem antes de montar prompt
            image_path = context.pop("image_path", None)
            prompt_completo = self._build_prompt(prompt, context)

            # Se tem imagem, instrui a ler o arquivo
            if image_path:
                prompt_completo = (
                    f"O usuario enviou uma imagem: {image_path}\n"
                    f"Leia o arquivo da imagem para analisar o conteudo visual.\n\n"
                    f"{prompt_completo}"
                )

            conversation_id = context.get("demand_id", "")
            max_turns = context.get("max_turns", 30)
            timeout = context.get("timeout", self._timeout)
            resultado = await self._execute_sdk(
                prompt_completo,
                conversation_id,
                max_turns,
                agent_name,
                timeout,
            )
            self._status = AgentStatus.DONE
            return resultado

        except asyncio.TimeoutError:
            self._status = AgentStatus.ERROR
            raise TimeoutError(f"Claude Agent SDK excedeu timeout de {self._timeout}s")
        except Exception as e:
            self._status = AgentStatus.ERROR
            raise RuntimeError(f"Erro no Claude Agent SDK: {e}") from e
        finally:
            # Restaura modelo original após model routing
            if model_override:
                self._model = original_model

    # Configuração de retry (alinhado com common/retry)
    MAX_RETRIES = 3

    async def _execute_sdk(
        self,
        prompt: str,
        conversation_id: str = "",
        max_turns: int = 30,
        agent_name: str = "",
        timeout: int = 0,
    ) -> str:
        """Executa query via SDK com retry e backoff exponencial.

        Tratamento especial para context_length_exceeded:
        comprime o prompt e retenta.
        """
        effective_timeout = timeout or self._timeout
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES + 1):
            options = self._build_options(conversation_id, max_turns, agent_name)

            try:
                partes_texto: list[str] = []
                session_id = None

                async with asyncio.timeout(effective_timeout):
                    async for message in query(prompt=prompt, options=options):
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, TextBlock):
                                    partes_texto.append(block.text)
                        elif isinstance(message, ResultMessage):
                            session_id = message.session_id

                # Salva session_id para retomada futura
                if session_id and conversation_id:
                    self._sessions[conversation_id] = session_id
                    logger.info(
                        "Sessao salva: %s → %s",
                        conversation_id,
                        session_id[:16] + "...",
                    )

                return "\n".join(partes_texto).strip()

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                # Context length exceeded: comprime prompt e retenta
                if "context_length_exceeded" in error_msg or "too long" in error_msg:
                    logger.warning(
                        "[%s] Context length exceeded (tentativa %d/%d). Comprimindo prompt...",
                        agent_name,
                        attempt + 1,
                        self.MAX_RETRIES + 1,
                    )
                    prompt = self._compress_prompt(prompt)
                    # Limpa sessao para forcar nova conversa
                    if conversation_id and conversation_id in self._sessions:
                        del self._sessions[conversation_id]
                    continue

                # Timeout: não faz retry (já consumiu o tempo)
                if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
                    raise

                # Outros erros: retry com backoff se transiente
                if not is_transient_error(e) or attempt >= self.MAX_RETRIES:
                    raise

                delay = 2 * (2**attempt)  # backoff: 2, 4, 8
                logger.warning(
                    "[%s] Erro transiente (tentativa %d/%d): %s. Retry em %ds...",
                    agent_name,
                    attempt + 1,
                    self.MAX_RETRIES + 1,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)

        # Nunca deve chegar aqui, mas para segurança
        raise last_error or RuntimeError("Falha apos todas as tentativas")

    @staticmethod
    def _compress_prompt(prompt: str) -> str:
        """Comprime prompt removendo seções menos críticas.

        Estratégia: remove seções de contexto intermediárias,
        mantendo instruções do sistema e mensagem do usuário.
        """
        lines = prompt.split("\n")
        total = len(lines)

        if total <= 50:
            # Prompt curto: mantém início e fim, remove o meio
            keep = total // 3
            removed = total - (keep * 2)
            return "\n".join(
                lines[:keep]
                + [f"\n[... {removed} linhas de contexto comprimido ...]\n"]
                + lines[-keep:]
            )

        # Remove metade das linhas intermediárias
        keep_start = total // 4
        keep_end = total // 4
        removed = total - keep_start - keep_end

        compressed = (
            lines[:keep_start]
            + [f"\n[... {removed} linhas de contexto removidas para caber no limite ...]\n"]
            + lines[-keep_end:]
        )
        return "\n".join(compressed)

    def _build_add_dirs(self, agent_name: str = "") -> list[str]:
        """Monta lista de diretorios adicionais para skills.

        3 niveis de skills:
        1. Projeto: /workspace/.claude/skills/ (via cwd, automatico)
        2. Agente: /app/agents/<agent_name>/ (skills + AGENTS.md)
        3. Globais: /app/global-skills/ (compartilhadas)
        """
        dirs: list[str] = []

        # Skills do agente
        if agent_name and self._agents_dir:
            agent_path = Path(self._agents_dir) / agent_name
            if agent_path.exists():
                dirs.append(str(agent_path))

        # Skills globais
        if self._global_skills_dir:
            global_path = Path(self._global_skills_dir)
            if global_path.exists():
                dirs.append(str(global_path))

        return dirs

    def _build_options(
        self,
        conversation_id: str = "",
        max_turns: int = 30,
        agent_name: str = "",
    ) -> ClaudeAgentOptions:
        """Constroi opcoes do SDK. Retoma sessao se existir."""
        kwargs: dict[str, Any] = {
            "max_turns": max_turns,
            "permission_mode": "bypassPermissions",
        }

        # Captura stderr do subprocess via callback (evita poluir o terminal no modo TUI)
        if self._stderr_to_log:
            def _log_stderr(line: str) -> None:
                logger.debug("[claude-cli] %s", line.rstrip())

            kwargs["stderr"] = _log_stderr

        if self._working_dir:
            kwargs["cwd"] = Path(self._working_dir)

        if self._model:
            kwargs["model"] = self._model

        # Diretorios adicionais para skills (agente + globais)
        add_dirs = self._build_add_dirs(agent_name)
        if add_dirs:
            kwargs["add_dirs"] = add_dirs

        # MCP server com todas as tools
        kwargs["mcp_servers"] = {"ai-squad-tools": self._mcp_server}

        # Allowed tools inclui todas as tools MCP
        tools = list(self._allowed_tools)
        for t in _TOOL_NAMES:
            if t not in tools:
                tools.append(t)
        kwargs["allowed_tools"] = tools

        # Retoma sessao existente
        if conversation_id and conversation_id in self._sessions:
            kwargs["resume"] = self._sessions[conversation_id]
            logger.info("Retomando sessao: %s", conversation_id)

        # Subagentes do Squad Lead
        if self._agent_definitions:
            kwargs["agents"] = self._agent_definitions

        return ClaudeAgentOptions(**kwargs)

    def _build_prompt(self, prompt: str, context: dict[str, Any]) -> str:
        """Monta prompt completo incluindo contexto."""
        return build_prompt(prompt, context)

    def get_session_id(self, conversation_id: str) -> str | None:
        """Retorna session_id de uma conversa ativa."""
        return self._sessions.get(conversation_id)

    def clear_session(self, conversation_id: str) -> None:
        """Remove sessao de uma conversa."""
        self._sessions.pop(conversation_id, None)

    async def ask(self, question: str) -> str:
        """Faz uma pergunta ao Claude Agent SDK."""
        return await self.run(question, {})

    def status(self) -> AgentStatus:
        """Retorna o status atual do adapter."""
        return self._status

    def on_human_needed(self, callback: Callable[..., Any]) -> None:
        """Registra callback para intervencao humana."""
        self._human_needed_callback = callback

    async def request_human_approval(self, question: str) -> str:
        """Solicita aprovacao humana via callback registrado."""
        if self._human_needed_callback is None:
            raise RuntimeError("Nenhum callback registrado para intervencao humana")

        self._status = AgentStatus.WAITING_HUMAN
        resultado = await self._human_needed_callback(question)
        self._status = AgentStatus.RUNNING
        return resultado
