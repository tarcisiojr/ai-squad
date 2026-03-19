"""Gerenciamento de agentes em background — extraído do engine.

Responsável por iniciar, monitorar e verificar agentes que rodam
como asyncio tasks em background.
"""

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, Awaitable

from src.adapters.interface import AIAgentAdapter
from src.messaging.interface import MessageBus
from src.orchestrator.context import WorkspaceContextCollector
from src.orchestrator.conversation import ConversationStore
from src.orchestrator.daily_notes import DailyNotes
from src.orchestrator.journal import JournalStore
from src.orchestrator.lessons import LessonsStore
from src.orchestrator.model_router import resolve_model_for_tier
from src.orchestrator.prompt_builder import (
    _get_agent_label,
    get_demand_state_summary,
    get_running_agents_status,
    read_agents_md,
)
from src.orchestrator.state import StateManager
from src.orchestrator.tools import RunningAgent

logger = logging.getLogger("ai-squad.agent-runner")


class AgentRunner:
    """Gerencia agentes em background: start, retry, verificação e status.

    Mantém o estado dos agentes rodando e delega callbacks ao engine
    quando um agente conclui.
    """

    def __init__(
        self,
        adapter: AIAgentAdapter,
        message_bus: MessageBus,
        personas: dict,
        agents_dir: Path,
        workspace: str,
        agent_timeout: int,
        context_collector: WorkspaceContextCollector,
        conversation: ConversationStore,
        journal: JournalStore,
        lessons: LessonsStore,
        daily_notes: DailyNotes,
        state_manager: StateManager,
        on_squad_lead_trigger: Callable[["RunningAgent", str], Awaitable[None]],
        keep_typing_callback: Callable[[str, str], Coroutine[Any, Any, None]],
    ) -> None:
        self._adapter = adapter
        self._message_bus = message_bus
        self._personas = personas
        self._agents_dir = agents_dir
        self._workspace = workspace
        self._agent_timeout = agent_timeout
        self._context_collector = context_collector
        self._conversation = conversation
        self._journal = journal
        self._lessons = lessons
        self._daily_notes = daily_notes
        self._state_manager = state_manager
        self._on_squad_lead_trigger = on_squad_lead_trigger
        self._keep_typing_and_feedback = keep_typing_callback
        self._light_model: str | None = None
        self._heavy_model: str | None = None
        self._default_model: str | None = None
        self._pipeline_executor: Any = None  # referência ao PipelineExecutor

        # Agentes em background: agent_name → RunningAgent
        self._running_agents: dict[str, RunningAgent] = {}

    @property
    def running_agents(self) -> dict[str, RunningAgent]:
        """Retorna agentes em execução (leitura)."""
        return self._running_agents

    def configure_models(
        self,
        light_model: str | None = None,
        heavy_model: str | None = None,
        default_model: str | None = None,
    ) -> None:
        """Configura modelos para roteamento por model_tier."""
        self._light_model = light_model
        self._heavy_model = heavy_model
        self._default_model = default_model

    def set_pipeline_executor(self, executor: Any) -> None:
        """Define referência ao PipelineExecutor para consultar model_tier."""
        self._pipeline_executor = executor

    def _resolve_model_for_agent(self, agent_name: str, demand_id: str) -> str | None:
        """Resolve modelo baseado no model_tier do step atual do pipeline."""
        if not self._pipeline_executor or not demand_id:
            return None

        step_config = self._pipeline_executor.get_current_step(demand_id)
        if not step_config:
            return None

        # Verifica se o agente pertence a este step
        step_agents = step_config.agents or ([step_config.agent] if step_config.agent else [])
        if agent_name not in step_agents:
            return None

        model = resolve_model_for_tier(
            step_config.model_tier,
            light_model=self._light_model,
            heavy_model=self._heavy_model,
            default_model=self._default_model,
        )
        if model:
            logger.info(
                "[%s] model_tier=%s → model=%s",
                agent_name,
                step_config.model_tier,
                model,
            )
        return model

    # --- Helpers ---

    def get_agent_label(self, agent_name: str) -> str:
        """Retorna label do agente a partir das personas da config."""
        return _get_agent_label(agent_name, self._personas)

    def _get_agent_timeout(self, agent_name: str) -> int:
        """Retorna timeout especifico por agente.

        Prioridade: config do agente (timeout no config.yaml) > agent_timeout padrao
        """
        persona = self._personas.get(agent_name)
        if persona and hasattr(persona, "timeout") and persona.timeout > 0:
            return persona.timeout
        return self._agent_timeout

    def _read_agents_md(self, agent_name: str) -> str:
        """Le o AGENTS.md de um agente."""
        return read_agents_md(agent_name, self._agents_dir)

    @staticmethod
    def _format_elapsed(seconds: int) -> str:
        """Formata tempo decorrido em formato legivel."""
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        secs = seconds % 60
        if secs:
            return f"{minutes}min{secs}s"
        return f"{minutes}min"

    # --- Agentes em background ---

    def start_background(
        self,
        agent_name: str,
        prompt: str,
        demand_id: str,
        user_id: str,
        thread_id: str | None = None,
    ) -> None:
        """Inicia agente como asyncio task em background."""
        running = RunningAgent(
            agent_name=agent_name,
            demand_id=demand_id,
            user_id=user_id,
            thread_id=thread_id,
            started_at=time.time(),
            status="running",
        )

        async def _run() -> str:
            return await self.run_agent_work(
                agent_name,
                prompt,
                demand_id,
                user_id,
            )

        task = asyncio.create_task(_run())
        running.task = task
        self._running_agents[agent_name] = running

        # Callback quando conclui
        task.add_done_callback(lambda t: asyncio.create_task(self.on_agent_done(agent_name, t)))

        logger.info("[%s] Agente iniciado em background (demand: %s)", agent_name, demand_id)

    async def run_agent_work(
        self,
        agent_name: str,
        prompt: str,
        demand_id: str,
        user_id: str,
    ) -> str:
        """Executa o trabalho do agente — roda em background task."""
        agents_md = self._read_agents_md(agent_name)
        timeout = self._get_agent_timeout(agent_name)

        # Injeta licoes aprendidas relevantes no prompt do agente
        lessons = self._lessons.format_for_prompt(prompt)
        if lessons:
            agents_md = f"{agents_md}\n\n{lessons}"

        context: dict[str, Any] = {
            "demand_id": demand_id,
            "agent_name": agent_name,
            "fase": "execucao",
            "system_instructions": agents_md,
            "timeout": timeout,
        }

        # Resolve modelo pelo model_tier do step do pipeline
        model_override = self._resolve_model_for_agent(agent_name, demand_id)
        if model_override:
            context["model_override"] = model_override

        logger.info("[%s] Timeout configurado: %ds", agent_name, timeout)

        # Coleta contexto do projeto + submodulos do agente
        persona = self._personas.get(agent_name)
        submodule_paths = []
        if persona and hasattr(persona, "submodules") and persona.submodules:
            submodule_paths = [sub.path for sub in persona.submodules if sub.path]
            logger.info("[%s] Submodulos: %s", agent_name, submodule_paths)

        # Coleta contexto de cada submodulo
        context_parts = []
        if submodule_paths:
            for sub_path in submodule_paths:
                sub_ctx = self._context_collector.collect(submodule_path=sub_path)
                if sub_ctx:
                    context_parts.append(sub_ctx)
        else:
            base_ctx = self._context_collector.collect()
            if base_ctx:
                context_parts.append(base_ctx)

        if context_parts:
            context["workspace_context"] = "\n\n".join(context_parts)

        # Cria diretorio de specs (apenas para agentes de trabalho, não para squad-lead)
        if agent_name != "squad-lead":
            specs_dir = Path(self._workspace) / "specs" / demand_id
            specs_dir.mkdir(parents=True, exist_ok=True)

        # Inicia typing + feedback background para este agente
        typing_task = asyncio.create_task(self._keep_typing_and_feedback(user_id, agent_name))

        try:
            resultado = await self._adapter.run(prompt, context)
        finally:
            typing_task.cancel()

        return resultado

    async def on_agent_done(self, agent_name: str, task: asyncio.Task) -> None:
        """Callback quando agente background conclui."""
        running = self._running_agents.get(agent_name)
        if not running:
            return

        label = self.get_agent_label(agent_name)
        user_id = running.user_id

        try:
            resultado = task.result()
            running.result = resultado
            running.status = "done"
            logger.info("[%s] Agente concluiu em background", agent_name)

            # Registra na nota diária
            self._daily_notes.add_agent_event(
                agent_name,
                f"Concluiu com sucesso ({running.elapsed_str()})",
            )

            # Registra no journal
            if running.demand_id:
                self._journal.add_decision(
                    running.demand_id,
                    f"{agent_name}_completed",
                    f"Agente concluiu em {running.elapsed_str()}",
                )

            preview = resultado
            if len(preview) > 2000:
                preview = preview[:2000] + "..."

            # Salva resultado do agente no historico de conversa
            if running.demand_id:
                self._conversation.save_message(
                    running.demand_id,
                    "assistant",
                    f"{agent_name} concluiu: {preview[:500]}",
                    agent_name=agent_name,
                )

            await self._message_bus.send_message(
                user_id,
                f"Concluido!\n\n{preview}",
                sender=label,  # type: ignore[call-arg]
                thread_id=running.thread_id,
            )

            # Dispara Squad Lead com contexto completo
            await self._on_squad_lead_trigger(
                running,
                f"O agente {label} concluiu com sucesso. Decida o proximo passo.",
            )

        except Exception as e:
            running.status = "error"
            running.error = str(e)
            logger.error("[%s] Agente falhou em background: %s", agent_name, e)

            # Registra erro na nota diária
            self._daily_notes.add_agent_event(
                agent_name,
                f"Erro: {str(e)[:100]}",
            )

            # Registra licao aprendida com o erro
            self._lessons.add(
                category="bug",
                problem=f"{agent_name} falhou com erro: {str(e)[:200]}",
                solution=f"Verificar prerequisitos antes de iniciar {agent_name}",
                agent_name=agent_name,
                demand_id=running.demand_id,
            )

            await self._message_bus.send_message(
                user_id,
                f"Erro: {e}",
                sender=label,  # type: ignore[call-arg]
                thread_id=running.thread_id,
            )

            await self._on_squad_lead_trigger(
                running,
                f"O agente {label} falhou com erro: {e}. Decida o que fazer.",
            )

    def get_status(self) -> str:
        """Retorna status formatado de todos os agentes."""
        return get_running_agents_status(self._running_agents, self._personas)

    def get_demand_state_summary(self) -> str:
        """Retorna resumo do estado de todas as demandas ativas."""
        return get_demand_state_summary(
            self._journal,
            self._state_manager,
            self._running_agents,
            self._personas,
        )
