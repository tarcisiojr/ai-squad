"""Gerenciamento de agentes em background — extraído do engine.

Responsável por iniciar, monitorar e verificar agentes que rodam
como asyncio tasks em background.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.common.retry import is_transient_error, retry_with_backoff
from ai_squad.factory import AgentConfig
from ai_squad.messaging.interface import MessageBus
from ai_squad.orchestrator.context import WorkspaceContextCollector
from ai_squad.orchestrator.conversation import ConversationStore
from ai_squad.orchestrator.daily_notes import DailyNotes
from ai_squad.orchestrator.graph import GraphStore
from ai_squad.orchestrator.journal import JournalStore
from ai_squad.orchestrator.lessons import LessonsStore
from ai_squad.orchestrator.model_router import resolve_model_for_tier
from ai_squad.orchestrator.prompt_builder import (
    get_agent_label,
    get_demand_state_summary,
    get_running_agents_status,
    read_agents_md,
)
from ai_squad.orchestrator.state import StateManager
from ai_squad.orchestrator.tools import RunningAgent

logger = logging.getLogger("ai-squad.agent-runner")


def is_transient_not_timeout(error: Exception) -> bool:
    """Verifica se o erro é transiente mas NÃO é timeout de execução.

    Timeout NÃO é retentado — já consumiu todo o tempo alocado,
    retentar provavelmente resulta no mesmo timeout.
    """
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return False
    return is_transient_error(error)


@dataclass(frozen=True)
class RunnerContext:
    """Agrupa dependências do AgentRunner para reduzir parâmetros do construtor.

    Campos essenciais (obrigatórios para execução):
        adapter, message_bus, personas, agents_dir, workspace, agent_timeout

    Stores (usados diretamente — candidatos a migrar para callbacks):
        context_collector, conversation, journal, lessons, daily_notes,
        state_manager, graph

    Callbacks opcionais (alternativa aos stores — engine pode sobrescrever):
        on_agent_success — chamado quando agente conclui com sucesso
        on_agent_error — chamado quando agente falha
        Quando definidos, substituem o acesso direto aos stores para
        journal/daily_notes/conversation/lessons no on_agent_done.
    """

    # --- Essenciais ---
    adapter: AIAgentAdapter
    message_bus: MessageBus
    personas: dict[str, AgentConfig]
    agents_dir: Path
    workspace: str
    agent_timeout: int

    # --- Stores (manter para compatibilidade, migrar gradualmente) ---
    context_collector: WorkspaceContextCollector
    conversation: ConversationStore
    journal: JournalStore
    lessons: LessonsStore
    daily_notes: DailyNotes
    state_manager: StateManager
    graph: GraphStore

    # --- Callbacks opcionais (substituem acesso direto a stores) ---
    on_agent_success: Callable[[str, str, str, str], Awaitable[None]] | None = None
    on_agent_error: Callable[[str, str, str], Awaitable[None]] | None = None


class AgentRunner:
    """Gerencia agentes em background: start, retry, verificação e status.

    Mantém o estado dos agentes rodando e delega callbacks ao engine
    quando um agente conclui.
    """

    def __init__(
        self,
        ctx: RunnerContext,
        on_squad_lead_trigger: Callable[[RunningAgent, str], Awaitable[None]],
        keep_typing_callback: Callable[[str, str], Coroutine[Any, Any, None]],
    ) -> None:
        self._ctx = ctx
        self._on_squad_lead_trigger = on_squad_lead_trigger
        self._keep_typing_and_feedback = keep_typing_callback
        self._light_model: str | None = None
        self._heavy_model: str | None = None
        self._default_model: str | None = None
        self._pipeline_executor: Any = None  # referência ao PipelineExecutor

        # Agentes em background: agent_name → RunningAgent
        self._running_agents: dict[str, RunningAgent] = {}
        # Contador de auto-recovery por agente (evita loops infinitos)
        self._recovery_count: dict[str, int] = {}

        # Circuit breaker: pausa sistema após falhas consecutivas
        self._consecutive_failures: int = 0
        self._CIRCUIT_BREAKER_THRESHOLD: int = 3
        self._circuit_open: bool = False

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

    def reset_circuit_breaker(self) -> None:
        """Reseta circuit breaker — chamado quando o usuário envia nova mensagem."""
        if self._circuit_open:
            logger.info("Circuit breaker resetado por mensagem do usuario")
        self._circuit_open = False
        self._consecutive_failures = 0

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
        return get_agent_label(agent_name, self._ctx.personas)

    def _get_agent_timeout(self, agent_name: str) -> int:
        """Retorna timeout especifico por agente.

        Prioridade: config do agente (timeout no config.yaml) > agent_timeout padrao
        """
        persona = self._ctx.personas.get(agent_name)
        if persona and hasattr(persona, "timeout") and persona.timeout > 0:
            return persona.timeout
        return self._ctx.agent_timeout

    def _read_agents_md(self, agent_name: str) -> str:
        """Le o AGENTS.md de um agente."""
        return read_agents_md(agent_name, self._ctx.agents_dir)

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

        # Ativa indicador de atividade do agente (spinner na TUI)
        label = self.get_agent_label(agent_name)
        self._ctx.message_bus.mark_agent_active(label)

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
        lessons = self._ctx.lessons.format_for_prompt(prompt)
        if lessons:
            agents_md = f"{agents_md}\n\n{lessons}"

        # Injeta contexto relacional do grafo de conhecimento
        graph_context = self._ctx.graph.format_for_prompt(prompt)
        if graph_context:
            agents_md = f"{agents_md}\n\n{graph_context}"

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
        persona = self._ctx.personas.get(agent_name)
        submodule_paths: list[str] = []
        if persona and hasattr(persona, "submodules") and persona.submodules:
            submodule_paths = [sub.path for sub in persona.submodules if sub.path]
            logger.info("[%s] Submodulos: %s", agent_name, submodule_paths)

        # Coleta contexto de cada submodulo
        context_parts: list[str] = []
        if submodule_paths:
            for sub_path in submodule_paths:
                sub_ctx = self._ctx.context_collector.collect(submodule_path=sub_path)
                if sub_ctx:
                    context_parts.append(sub_ctx)
        else:
            base_ctx = self._ctx.context_collector.collect()
            if base_ctx:
                context_parts.append(base_ctx)

        if context_parts:
            context["workspace_context"] = "\n\n".join(context_parts)

        # Cria diretorio de specs (apenas para agentes de trabalho, não para squad-lead)
        if agent_name != "squad-lead":
            specs_dir = Path(self._ctx.workspace) / "specs" / demand_id
            specs_dir.mkdir(parents=True, exist_ok=True)

        # Inicia typing + feedback background para este agente
        typing_task = asyncio.create_task(self._keep_typing_and_feedback(user_id, agent_name))

        try:
            resultado = await self._run_with_retry(agent_name, prompt, context)
        finally:
            typing_task.cancel()

        return resultado

    async def _run_with_retry(
        self,
        agent_name: str,
        prompt: str,
        context: dict[str, Any],
    ) -> str:
        """Executa adapter.run() com retry e backoff para erros transientes."""
        return await retry_with_backoff(
            lambda: self._ctx.adapter.run(prompt, context),
            max_retries=2,
            base_delay=2.0,
            is_transient=is_transient_not_timeout,
        )

    async def on_agent_done(self, agent_name: str, task: asyncio.Task[str]) -> None:
        """Callback quando agente background conclui.

        Estruturado em duas fases para separar erros do agente de erros do Squad Lead:
        - Phase 1: extrai resultado do agente (try/except trata apenas erros do agente)
        - Phase 2: dispara Squad Lead (fora do try, não corrompe status do agente)
        """
        running = self._running_agents.get(agent_name)
        if not running:
            return

        label = self.get_agent_label(agent_name)

        # Desativa indicador de atividade do agente (spinner na TUI)
        self._ctx.message_bus.mark_agent_idle(label)

        # --- Phase 1: Resultado do agente ---
        event_context: str | None = None

        try:
            resultado = task.result()
            running.result = resultado
            running.status = "done"
            logger.info("[%s] Agente concluiu em background", agent_name)

            preview = resultado
            if len(preview) > 2000:
                preview = preview[:2000] + "..."

            # Registra sucesso nos stores (via callback ou acesso direto)
            if self._ctx.on_agent_success:
                await self._ctx.on_agent_success(
                    agent_name,
                    running.demand_id or "",
                    running.elapsed_str(),
                    preview,
                )
            else:
                self._record_agent_success(
                    agent_name, running.demand_id, running.elapsed_str(), preview
                )

            # Monta contexto para o Squad Lead
            progress_summary = ""
            if running.progress_log:
                recent = running.progress_log[-5:]
                progress_summary = "\nProgresso reportado pelo agente:\n" + "\n".join(
                    f"- {p}" for p in recent
                )

            event_context = (
                f"O agente {label} concluiu com sucesso.\n\n"
                f"RESULTADO (apresente de forma concisa ao usuario, sem repetir literalmente):\n"
                f"{preview}{progress_summary}\n\n"
                f"Decida o proximo passo."
            )

        except Exception as e:
            running.status = "error"
            running.error = str(e)
            logger.error("[%s] Agente falhou em background: %s", agent_name, e)

            # Registra erro nos stores (via callback ou acesso direto)
            if self._ctx.on_agent_error:
                await self._ctx.on_agent_error(
                    agent_name,
                    running.demand_id or "",
                    str(e),
                )
            else:
                self._record_agent_error(agent_name, running.demand_id, e)

            # Atualiza pipeline state com o erro do agente
            if self._pipeline_executor and running.demand_id:
                try:
                    pip_state = self._pipeline_executor.load_state(running.demand_id)
                    current_step_id = pip_state.current_step if pip_state else ""
                    if current_step_id:
                        self._pipeline_executor.update_agent_status(
                            running.demand_id,
                            current_step_id,
                            agent_name,
                            "error",
                        )
                except Exception:
                    pass

            # Monta contexto de erro para o Squad Lead
            is_timeout = isinstance(e, (asyncio.TimeoutError, TimeoutError))
            if is_timeout:
                error_desc = f"O agente {label} excedeu o tempo limite."
            else:
                error_desc = f"O agente {label} falhou com erro: {e}."

            event_context = (
                f"{error_desc}\nDecida o que fazer (retentar, escalar, ou informar o usuario)."
            )

        # --- Phase 2: Dispara Squad Lead (fora do try/except do agente) ---
        if event_context:
            await self._on_squad_lead_trigger(running, event_context)

    _AUTO_RECOVERY_DELAY = 30  # segundos
    _MAX_AUTO_RECOVERY = 2  # tentativas máximas

    def _record_agent_success(
        self,
        agent_name: str,
        demand_id: str | None,
        elapsed: str,
        preview: str,
    ) -> None:
        """Registra sucesso do agente nos stores (fallback quando callback ausente)."""
        self._ctx.daily_notes.add_agent_event(
            agent_name,
            f"Concluiu com sucesso ({elapsed})",
        )
        if demand_id:
            self._ctx.journal.add_decision(
                demand_id,
                f"{agent_name}_completed",
                f"Agente concluiu em {elapsed}",
            )
            self._ctx.conversation.save_message(
                demand_id,
                "internal",
                f"{agent_name} concluiu: {preview[:500]}",
                agent_name=agent_name,
            )

    def _record_agent_error(
        self,
        agent_name: str,
        demand_id: str | None,
        error: Exception,
    ) -> None:
        """Registra erro do agente nos stores (fallback quando callback ausente)."""
        self._ctx.daily_notes.add_agent_event(
            agent_name,
            f"Erro: {str(error)[:100]}",
        )
        self._ctx.lessons.add(
            category="bug",
            problem=f"{agent_name} falhou com erro: {str(error)[:200]}",
            solution=f"Verificar prerequisitos antes de iniciar {agent_name}",
            agent_name=agent_name,
            demand_id=demand_id or "",
        )

    async def schedule_auto_recovery(
        self,
        running: RunningAgent,
        error_desc: str,
    ) -> None:
        """Agenda retomada automática do Squad Lead após falha.

        Estratégia em 3 níveis:
        1. Retomada simples (até 2x com 30s de delay)
        2. Escalação inteligente — Squad Lead com prompt para mudar estratégia
        3. Notificação ao usuário pedindo intervenção

        Inclui circuit breaker: após falhas consecutivas, pausa o sistema.
        """
        # Circuit breaker: incrementa falhas consecutivas
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open = True
            logger.warning(
                "Circuit breaker aberto apos %d falhas consecutivas",
                self._consecutive_failures,
            )
            user_id = running.user_id
            if user_id:
                try:
                    await self._ctx.message_bus.send_message(
                        user_id,
                        "Sistema pausado após falhas consecutivas. "
                        "Envie nova mensagem para retomar.",
                        thread_id=running.thread_id,
                    )
                except Exception:
                    logger.error("Falha ao notificar usuario sobre circuit breaker")
            return

        agent_key = running.agent_name
        retries = self._recovery_count.get(agent_key, 0)

        if retries >= self._MAX_AUTO_RECOVERY:
            # Nível 2: Escalação inteligente — pede ao Squad Lead para mudar estratégia
            logger.info(
                "[%s] Auto-recovery esgotado. Tentando escalação inteligente.",
                agent_key,
            )
            self._recovery_count.pop(agent_key, None)
            await self._escalate_to_squad_lead(running, error_desc, retries)
            return

        self._recovery_count[agent_key] = retries + 1

        # Nível 1: Retomada simples
        logger.info(
            "[%s] Auto-recovery agendado em %ds (tentativa %d/%d)",
            agent_key,
            self._AUTO_RECOVERY_DELAY,
            retries + 1,
            self._MAX_AUTO_RECOVERY,
        )
        await asyncio.sleep(self._AUTO_RECOVERY_DELAY)

        try:
            await self._on_squad_lead_trigger(
                running,
                (
                    f"RETOMADA AUTOMATICA: {error_desc}\n"
                    f"Avalie o estado da demanda e retome o trabalho. "
                    f"Use get_pipeline_state() para verificar o pipeline."
                ),
            )
            # Recovery funcionou — reseta contador
            self._recovery_count.pop(agent_key, None)
        except Exception as e:
            logger.error(
                "[%s] Auto-recovery falhou (tentativa %d): %s",
                agent_key,
                retries + 1,
                e,
            )

    async def _escalate_to_squad_lead(
        self,
        running: RunningAgent,
        error_desc: str,
        previous_retries: int,
    ) -> None:
        """Escalação inteligente: pede ao Squad Lead para mudar de estratégia.

        Dispara com um prompt especial que instrui o Squad Lead a tentar
        uma abordagem diferente (dividir trabalho, simplificar, pular step).
        Se a escalação também falhar, notifica o usuário.
        """
        demand_id = running.demand_id or "desconhecida"
        label = self.get_agent_label(running.agent_name)

        escalation_prompt = (
            f"ESCALACAO: A demanda '{demand_id}' travou apos {previous_retries} "
            f"tentativas de retomada automatica.\n"
            f"Ultimo erro: {error_desc}\n\n"
            f"VOCE DEVE tentar uma abordagem diferente:\n"
            f"1. Use get_pipeline_state() para entender o estado atual\n"
            f"2. Se o step atual travou, considere: skip_step() para pular, "
            f"ou start_agent() com uma tarefa simplificada\n"
            f"3. Se o agente {label} falhou, tente dividir o trabalho "
            f"ou delegar para outro agente\n"
            f"4. Se nenhuma alternativa funcionar, informe o usuario "
            f"o que voce tentou e peca orientacao\n\n"
            f"NAO repita a mesma estrategia que ja falhou."
        )

        # Espera um pouco antes da escalação
        await asyncio.sleep(self._AUTO_RECOVERY_DELAY)

        try:
            await self._on_squad_lead_trigger(running, escalation_prompt)
            logger.info("[%s] Escalação inteligente aceita pelo Squad Lead", running.agent_name)
        except Exception as e:
            # Nível 3: Escalação falhou — notifica usuário pedindo intervenção
            logger.error(
                "[%s] Escalação inteligente falhou: %s. Notificando usuario.",
                running.agent_name,
                e,
            )
            user_id = running.user_id
            if user_id:
                try:
                    await self._ctx.message_bus.send_message(
                        user_id,
                        (
                            f"⚠️ A demanda `{demand_id}` travou após múltiplas tentativas.\n\n"
                            f"Último erro: {error_desc[:200]}\n\n"
                            f"Envie uma nova mensagem para retomar o processamento."
                        ),
                        thread_id=running.thread_id,
                    )
                except Exception:
                    logger.error(
                        "[%s] Falha ao notificar usuario sobre escalação",
                        running.agent_name,
                    )

    def get_status(self) -> str:
        """Retorna status formatado de todos os agentes."""
        return get_running_agents_status(self._running_agents, self._ctx.personas)

    def get_demand_state_summary(self) -> str:
        """Retorna resumo do estado de todas as demandas ativas."""
        return get_demand_state_summary(
            self._ctx.journal,
            self._ctx.state_manager,
            self._running_agents,
            self._ctx.personas,
        )
