"""Motor de orquestração — runtime para o Squad Lead com delegação async."""

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.common.token_tracker import TokenTracker
from ai_squad.messaging.interface import MessageBus
from ai_squad.orchestrator.agent_runner import AgentRunner, RunnerContext
from ai_squad.orchestrator.context import WorkspaceContextCollector
from ai_squad.orchestrator.conversation import ConversationStore
from ai_squad.orchestrator.daily_notes import DailyNotes
from ai_squad.orchestrator.graph import GraphStore
from ai_squad.orchestrator.journal import JournalStore
from ai_squad.orchestrator.knowledge import KnowledgeStore
from ai_squad.orchestrator.lessons import LessonsStore
from ai_squad.orchestrator.media import extract_and_send_media
from ai_squad.orchestrator.model_router import select_model
from ai_squad.orchestrator.pipeline import PipelineLoader
from ai_squad.orchestrator.pipeline_handler import PipelineHandler
from ai_squad.orchestrator.pipeline_state import PipelineExecutor
from ai_squad.orchestrator.prompt_builder import (
    build_squad_lead_prompt,
    get_agents_summary,
    get_graph_context,
    get_knowledge_context,
    get_workspace_context_cached,
    read_agents_md_cached,
)
from ai_squad.orchestrator.reaction_tracker import ReactionTracker
from ai_squad.orchestrator.state import StateManager
from ai_squad.orchestrator.tools import RunningAgent

logger = logging.getLogger("ai-squad.engine")


@dataclass
class EngineStatus:
    """Status público do engine para consumo pelo daemon."""

    squad_lead_busy: bool = False
    squad_lead_since: float = 0.0
    current_demand_id: str = ""
    running_agents: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())
    personas: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())
    token_summary: str = ""


class OrchestrationEngine:
    """Motor de orquestração com delegação async.

    O Squad Lead usa chamadas SDK curtas (max_turns=5) e delega trabalho
    a agentes via MCP tools. Agentes rodam em background como asyncio tasks.
    """

    # Intervalo em segundos para reenviar "digitando..."
    TYPING_INTERVAL = 4
    # Intervalo em segundos para feedback periodico
    FEEDBACK_INTERVAL = 30
    # Limite de turnos antes de perguntar ao usuario se deseja finalizar
    MAX_CONVERSATIONAL_TURNS = 10
    # max_turns para o Squad Lead (precisa de margem para tools como Playwright + resposta)
    SQUAD_LEAD_MAX_TURNS = 15
    # Intervalo em segundos para enviar progresso ao usuario
    PROGRESS_STREAM_INTERVAL = 15
    # Quantidade de mensagens de progresso a enviar por ciclo
    PROGRESS_STREAM_COUNT = 3

    def __init__(
        self,
        adapter: AIAgentAdapter,
        message_bus: MessageBus,
        state_manager: StateManager,
        workspace: str = "/workspace",
        personas: dict[str, Any] | None = None,
        agents_dir: str = "/app/agents",
        agent_timeout: int = 300,
        light_model: str | None = None,
        heavy_model: str | None = None,
        pipeline_dir: str = "",
    ) -> None:
        self._adapter = adapter
        self._message_bus = message_bus
        self._state_manager = state_manager
        self._workspace = workspace
        self._personas = personas or {}
        self._agents_dir = Path(agents_dir)
        self._agent_timeout = agent_timeout
        self._light_model = light_model
        self._heavy_model = heavy_model
        self._context_collector = WorkspaceContextCollector(workspace)
        self._conversation = ConversationStore(state_manager.state_dir)
        self._journal = JournalStore(state_dir=state_manager.state_dir)
        self._lessons = LessonsStore(state_dir=state_manager.state_dir)
        self._daily_notes = DailyNotes(state_dir=state_manager.state_dir)
        self._graph = GraphStore(state_dir=state_manager.state_dir)

        # Rastreamento de consumo de tokens por chamada
        self._token_tracker = TokenTracker()

        # Knowledge base e reaction tracker (usados pelo preset helpdesk)
        self._knowledge: KnowledgeStore | None = None
        self._reaction_tracker: ReactionTracker | None = None
        # Pipeline declarativo (opcional — modo legado se não configurado)
        self._pipeline_executor: PipelineExecutor | None = None
        if pipeline_dir:
            loader = PipelineLoader(pipeline_dir)
            pipeline = loader.load()
            if pipeline:
                self._pipeline_executor = PipelineExecutor(
                    state_dir=state_manager.state_dir,
                    pipeline=pipeline,
                )
                logger.info(
                    "Pipeline carregado: %s (%d steps)",
                    pipeline.name,
                    len(pipeline.steps),
                )

        # Gerenciamento de agentes em background (extraído para módulo separado)
        runner_ctx = RunnerContext(
            adapter=adapter,
            message_bus=message_bus,
            personas=self._personas,
            agents_dir=self._agents_dir,
            workspace=workspace,
            agent_timeout=agent_timeout,
            context_collector=self._context_collector,
            conversation=self._conversation,
            journal=self._journal,
            lessons=self._lessons,
            daily_notes=self._daily_notes,
            state_manager=self._state_manager,
            graph=self._graph,
        )
        self._agent_runner = AgentRunner(
            ctx=runner_ctx,
            on_squad_lead_trigger=self._trigger_squad_lead_for_agent,
            keep_typing_callback=self._keep_typing_and_feedback,
        )
        self._running_agents = self._agent_runner.running_agents

        # Configura model routing por tier no AgentRunner
        self._agent_runner.configure_models(
            light_model=light_model,
            heavy_model=heavy_model,
        )
        if self._pipeline_executor:
            self._agent_runner.set_pipeline_executor(self._pipeline_executor)

        # Handler de pipeline (extraído do engine)
        self._pipeline_handler = PipelineHandler(
            pipeline_executor=self._pipeline_executor,
            journal=self._journal,
            graph=self._graph,
            get_demand_id=lambda: self._default_demand_id,
        )

        # user_id, demand_id e thread_id defaults (usados pelo Squad Lead)
        self._default_user_id: str = ""
        self._default_demand_id: str = ""
        self._default_thread_id: str | None = None
        # Mapeamento thread ↔ demand (injetado pelo daemon)
        self._thread_map: Any = None
        # Callback para criar tópico/thread (injetado pelo daemon)
        self._create_topic_callback: Callable[..., Coroutine[Any, Any, str | None]] | None = None

        # Monitor do Squad Lead: detecta respostas vazias consecutivas
        self._squad_lead_empty_count: int = 0
        self._squad_lead_max_empty: int = 3  # reseta sessao apos N respostas vazias

        # Semáforo: serializa chamadas ao Squad Lead (uma por vez)
        self._squad_lead_semaphore = asyncio.Semaphore(1)

        # Flag: Squad Lead está processando (visível no /status)
        self._squad_lead_busy: bool = False
        self._squad_lead_busy_since: float = 0.0

        # Registra callbacks no adapter via CallbackRegistry
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

        self._adapter.on_human_needed(self._handle_human_needed)
        self._adapter.on(EVENT_PROGRESS, self._handle_progress)
        self._adapter.on(EVENT_START_AGENT, self._handle_start_agent)
        self._adapter.on(EVENT_GET_AGENTS, self._handle_get_agents)
        self._adapter.on(EVENT_GET_DEMAND_STATE, self._handle_get_demand_state)
        self._adapter.on(EVENT_READ_JOURNAL, self._handle_read_journal)
        self._adapter.on(EVENT_SEND_IMAGE, self._handle_send_image)
        self._adapter.on(EVENT_LEARN_LESSON, self._handle_learn_lesson)
        self._adapter.on(EVENT_GET_PIPELINE_STATE, self._pipeline_handler.handle_get_pipeline_state)
        self._adapter.on(EVENT_ADVANCE_STEP, self._pipeline_handler.handle_advance_step)
        self._adapter.on(EVENT_SKIP_STEP, self._pipeline_handler.handle_skip_step)
        self._adapter.on(EVENT_RERUN_STEP, self._pipeline_handler.handle_rerun_step)
        self._adapter.on(EVENT_QUERY_GRAPH, self._handle_query_graph)

        # Registra callback de sumarização no conversation store
        self._conversation.set_summarize_callback(self._summarize_via_llm)

        # Registra callback de extração no grafo de conhecimento
        self._graph.set_extract_callback(self._summarize_via_llm)

    # --- API Pública ---

    def get_status(self) -> EngineStatus:
        """Retorna status público do engine para consumo pelo daemon."""
        return EngineStatus(
            squad_lead_busy=self._squad_lead_busy,
            squad_lead_since=self._squad_lead_busy_since,
            current_demand_id=self._default_demand_id,
            running_agents=dict(self._running_agents),
            personas=dict(self._personas),
            token_summary=self._token_tracker.summary(),
        )

    def set_thread_map(self, thread_map: Any) -> None:
        """Injeta mapeamento thread ↔ demand no engine."""
        self._thread_map = thread_map

    def set_create_topic_callback(self, cb: Callable[..., Coroutine[Any, Any, str | None]]) -> None:
        """Injeta callback para criação de tópico/thread."""
        self._create_topic_callback = cb

    def get_journal(self) -> JournalStore:
        """Retorna o JournalStore do engine."""
        return self._journal

    def get_running_agents_status(self) -> str:
        """Retorna status formatado dos agentes + Squad Lead (API pública)."""
        return self._get_running_agents_status()

    def get_running_agents(self) -> dict[str, Any]:
        """Retorna dict de agentes em execução."""
        return self._running_agents

    def get_agent_label(self, agent_name: str) -> str:
        """Retorna label do agente (delega ao AgentRunner)."""
        return self._agent_runner.get_agent_label(agent_name)

    def get_filtered_agents_status(self, agents: dict[str, Any], personas: dict[str, Any]) -> str:
        """Retorna status formatado para subset de agentes."""
        from ai_squad.orchestrator.prompt_builder import get_running_agents_status

        return get_running_agents_status(agents, personas)

    def stop_agent(self, agent_name: str) -> bool:
        """Para um agente pelo nome. Retorna True se cancelado."""
        ra = self._running_agents.get(agent_name)
        if not ra or ra.status != "running" or not ra.task:
            return False
        ra.task.cancel()
        ra.status = "cancelled"
        return True

    # --- Knowledge Base (helpdesk) ---

    def configure_knowledge(self, knowledge_dir: str, use_qmd: bool = False) -> None:
        """Configura knowledge base para o preset helpdesk."""
        self._knowledge = KnowledgeStore(knowledge_dir, use_qmd=use_qmd)
        self._reaction_tracker = ReactionTracker(knowledge_store=self._knowledge)
        logger.info("Knowledge base configurada: %s", knowledge_dir)

    @property
    def knowledge(self) -> KnowledgeStore | None:
        """Retorna knowledge store (se configurado)."""
        return self._knowledge

    @property
    def reaction_tracker(self) -> ReactionTracker | None:
        """Retorna reaction tracker (se configurado)."""
        return self._reaction_tracker

    # --- Sumarização de contexto ---

    async def _summarize_via_llm(self, text: str) -> str:
        """Sumariza texto via chamada curta ao LLM."""
        return await self._adapter.ask(text)

    async def _maybe_summarize(self, demand_id: str) -> None:
        """Tenta sumarizar conversa se necessário. Tolerante a falha."""
        try:
            done = await self._conversation.summarize_if_needed(demand_id)
            if done:
                logger.info("Conversa sumarizada para demand: %s", demand_id)
        except Exception as e:
            logger.warning("Falha ao sumarizar conversa: %s", e)

    # --- Helpers ---

    def _get_agents_summary(self) -> str:
        """Gera resumo de todos os agentes para o prompt do Squad Lead."""
        return get_agents_summary(self._personas, self._agents_dir)

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

    # --- MCP tool callbacks ---

    def _resolve_user_id(self, agent_name: str = "") -> str:
        """Resolve user_id — do agente em background ou default."""
        if agent_name and agent_name in self._running_agents:
            return self._running_agents[agent_name].user_id
        return self._default_user_id

    def _resolve_thread_id(self, agent_name: str = "") -> str | None:
        """Resolve thread_id — do agente em background ou default."""
        if agent_name and agent_name in self._running_agents:
            ra = self._running_agents[agent_name]
            # Primeiro tenta thread_id direto do RunningAgent
            if ra.thread_id is not None:
                return ra.thread_id
            # Fallback: resolve via thread_map a partir do demand_id
            if self._thread_map and ra.demand_id:
                return self._thread_map.get_thread(ra.demand_id)
        return self._default_thread_id

    async def _handle_progress(self, agent_name: str, message: str) -> None:
        """Recebe progresso do agente (via report_progress) e armazena internamente.

        O progresso vai para o progress_log do RunningAgent (canal interno).
        O spinner já é ativado no start_background via mark_agent_active.

        Tolerante a falha — nunca propaga excecao para nao matar o agente.
        """
        running = self._running_agents.get(agent_name)
        if running:
            running.progress_log.append(message)

    async def _handle_start_agent(self, agent_name: str, task_description: str) -> str:
        """Callback da MCP tool start_agent — inicia agente em background."""
        if agent_name not in self._personas:
            available = ", ".join(self._personas.keys())
            return f"Agente '{agent_name}' nao encontrado. Disponiveis: {available}"

        if agent_name in self._running_agents:
            ra = self._running_agents[agent_name]
            if ra.status == "running":
                return f"Agente '{agent_name}' ja esta rodando ({ra.elapsed_str()}). Aguarde conclusao."

        label = self._agent_runner.get_agent_label(agent_name)
        demand_id = self._default_demand_id
        user_id = self._default_user_id
        thread_id = self._default_thread_id

        # Em modo fórum, gera demand_id real e cria tópico (só na 1ª delegação)
        if demand_id == "squad-lead-session" and self._create_topic_callback:
            import re
            import unicodedata
            import uuid

            # Gera slug a partir da descrição
            normalized = unicodedata.normalize("NFKD", task_description)
            ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
            clean = re.sub(r"[^a-z0-9\s]", "", ascii_text.lower())
            words = clean.split()[:5]
            slug = "-".join(words) if words else "demanda"
            demand_id = f"{slug}-{uuid.uuid4().hex[:4]}"

            # Atualiza default ANTES de criar tópico — assim chamadas
            # subsequentes de start_agent na mesma run usam o mesmo demand_id
            self._default_demand_id = demand_id

            # Cria tópico via callback do daemon
            title = task_description[:128]
            try:
                new_thread_id = await self._create_topic_callback(demand_id, title)
                if new_thread_id:
                    thread_id = new_thread_id
                    self._default_thread_id = thread_id
                    logger.info("Demanda criada com tópico: %s (thread=%s)", demand_id, thread_id)
                else:
                    logger.warning(
                        "Falha ao criar tópico para demanda %s (sem permissão?)", demand_id
                    )
            except Exception as e:
                logger.error("Erro ao criar tópico: %s", e)

        # Cria journal se não existe
        if demand_id and not self._journal.read(demand_id):
            self._journal.create(demand_id, task_description)

        # Registra decisão no journal
        if demand_id:
            self._journal.add_decision(
                demand_id,
                f"delegated_to_{agent_name}",
                task_description,
            )
            self._journal.set_next_expected(
                demand_id,
                f"{agent_name}_completion",
                agent_name,
                f"{label} executando: {task_description[:100]}",
            )

        # Inicia agente em background
        self._agent_runner.start_background(
            agent_name,
            task_description,
            demand_id,
            user_id,
            thread_id=thread_id,
        )

        return f"Agente {label} iniciado em background. Voce sera notificado quando concluir."

    async def _handle_get_agents(self) -> str:
        """Callback da MCP tool get_running_agents."""
        return self._get_running_agents_status()

    async def _handle_get_demand_state(self) -> str:
        """Callback da MCP tool get_demand_state — estado de demandas ativas."""
        return self._get_demand_state_summary()

    async def _handle_read_journal(self) -> str:
        """Callback da MCP tool read_journal — journals ativos."""
        return self._journal.get_active_summaries()

    async def _handle_learn_lesson(
        self,
        category: str,
        problem: str,
        solution: str,
    ) -> None:
        """Callback da MCP tool learn_lesson — registra licao aprendida.

        Tolerante a falha.
        """
        try:
            self._lessons.add(
                category=category,
                problem=problem,
                solution=solution,
                agent_name=self._adapter._current_agent_name,  # type: ignore[attr-defined]
                demand_id=self._default_demand_id,
            )
            logger.info("Licao registrada: [%s] %s", category, problem[:60])

            # Alimenta grafo de conhecimento com a lição
            lesson_text = f"Licao [{category}]: {problem} → Solucao: {solution}"
            await self._graph.ingest(lesson_text, self._default_demand_id)
        except Exception as e:
            logger.warning("Falha ao registrar licao: %s", e)

    async def _handle_query_graph(self, query: str) -> str:
        """Callback da MCP tool query_knowledge_graph — consulta grafo de conhecimento."""
        if not query:
            return "Informe um termo para buscar no grafo."
        result = self._graph.format_for_prompt(query)
        if not result:
            return f"Nenhum conhecimento encontrado no grafo para: {query}"
        return result

    async def _handle_send_image(self, image_path: str, caption: str = "") -> None:
        """Callback da MCP tool send_image — envia imagem ao usuario via mensageria.

        Resolve caminhos relativos ao workspace. Tolerante a falha.
        """
        user_id = self._default_user_id
        if not user_id:
            return
        try:
            resolved = Path(image_path)
            if not resolved.is_absolute():
                resolved = Path(self._workspace) / image_path
            if not resolved.exists():
                logger.warning("Imagem nao encontrada: %s (resolvido: %s)", image_path, resolved)
                return
            thread_id = self._default_thread_id
            if hasattr(self._message_bus, "send_photo"):
                await self._message_bus.send_photo(
                    user_id,
                    str(resolved),
                    caption,
                    thread_id=thread_id,
                )
            else:
                logger.warning("MessageBus nao suporta envio de fotos")
        except Exception as e:
            logger.warning("Falha ao enviar imagem: %s", e)

    async def _extract_and_send_images(self, user_id: str, text: str) -> str:
        """Delega detecção de imagens/arquivos ao módulo media."""
        return await extract_and_send_media(user_id, text, self._message_bus, self._workspace)

    # --- Agentes em background (delegados ao AgentRunner) ---

    async def _trigger_squad_lead_for_agent(
        self,
        running: RunningAgent,
        event_context: str,
    ) -> None:
        """Dispara Squad Lead com contexto do agente que concluiu."""
        user_id = running.user_id or self._default_user_id
        demand_id = running.demand_id or self._default_demand_id
        thread_id = running.thread_id
        # Fallback: resolve via thread_map
        if thread_id is None and self._thread_map and demand_id:
            thread_id = self._thread_map.get_thread(demand_id)
        if not user_id or not demand_id:
            return

        # Alimenta grafo com resultado do agente
        if event_context and demand_id:
            agent_text = f"Agente {running.agent_name} concluiu: {event_context[:1000]}"
            await self._graph.ingest(agent_text, demand_id)

        try:
            await self.run_squad_lead(demand_id, user_id, event_context, thread_id=thread_id)
        except Exception as e:
            logger.error("Erro ao disparar Squad Lead para agente %s: %s", running.agent_name, e)
            # NÃO re-raise — run_squad_lead já notificou o usuário.
            # Agenda auto-recovery para retomar o loop.
            asyncio.create_task(
                self._agent_runner.schedule_auto_recovery(
                    running,
                    f"Squad Lead falhou ao processar resultado de {running.agent_name}: {e}",
                )
            )

    def _get_running_agents_status(self) -> str:
        """Retorna status dos agentes + Squad Lead."""
        parts: list[str] = []

        # Status do Squad Lead
        if self._squad_lead_busy:
            elapsed = int(time.time() - self._squad_lead_busy_since)
            sl_label = self._agent_runner.get_agent_label("squad-lead")
            if elapsed < 60:
                elapsed_str = f"{elapsed}s"
            else:
                mins = elapsed // 60
                secs = elapsed % 60
                elapsed_str = f"{mins}min{secs}s" if secs else f"{mins}min"
            parts.append(f"🧠 {sl_label}: processando ({elapsed_str})")

        # Status dos agentes em background
        agents_status = self._agent_runner.get_status()
        if agents_status != "Nenhum agente ativo no momento.":
            parts.append(agents_status)

        # Resumo de tokens consumidos na sessão
        token_summary = self._token_tracker.summary()
        if token_summary != "Nenhuma chamada registrada.":
            parts.append(f"📊 {token_summary}")

        if not parts:
            return "Nenhum agente ativo no momento."

        return "\n".join(parts)

    def _get_demand_state_summary(self) -> str:
        """Delega ao AgentRunner."""
        return self._agent_runner.get_demand_state_summary()

    # --- Squad Lead (chamadas curtas) ---

    def _build_squad_lead_prompt(
        self,
        demand_id: str,
        demand_text: str,
    ) -> str:
        """Wrapper fino — coleta dados e delega ao prompt_builder."""
        squad_md = read_agents_md_cached("squad-lead", self._agents_dir)
        agents_summary = self._get_agents_summary()
        running_status = self._get_running_agents_status()
        demand_state = self._get_demand_state_summary()
        conversation_history = self._conversation.format_history_for_prompt(demand_id)
        journal_summary = self._journal.get_active_summaries()
        lessons_context = self._lessons.format_for_prompt(demand_text)
        daily_notes_context = self._daily_notes.load_recent()
        graph_ctx = get_graph_context(self._graph, demand_text)
        knowledge_ctx = get_knowledge_context(self._knowledge, demand_text)
        pipeline_state = ""
        if self._pipeline_executor:
            pipeline_state = self._pipeline_executor.format_state_for_prompt(demand_id)
        workspace_context = get_workspace_context_cached(self._context_collector, self._workspace)

        return build_squad_lead_prompt(
            squad_md=squad_md,
            agents_summary=agents_summary,
            running_status=running_status,
            demand_state=demand_state,
            conversation_history=conversation_history,
            journal_summary=journal_summary,
            lessons_context=lessons_context,
            daily_notes_context=daily_notes_context,
            graph_context=graph_ctx,
            knowledge_context=knowledge_ctx,
            pipeline_state=pipeline_state,
            workspace_context=workspace_context,
            demand_text=demand_text,
        )

    async def run_squad_lead(
        self,
        demand_id: str,
        user_id: str,
        demand_text: str,
        image_path: str | None = None,
        thread_id: str | None = None,
    ) -> str:
        """Executa Squad Lead com chamada SDK curta.

        Serializa chamadas via semáforo — apenas uma execução por vez.
        Retorna a resposta do Squad Lead. Nao bloqueia — se o Squad Lead
        delegar via start_agent, o agente roda em background.
        """
        # Serializa acesso ao Squad Lead via semáforo
        try:
            await asyncio.wait_for(self._squad_lead_semaphore.acquire(), timeout=30.0)
        except asyncio.TimeoutError:
            await self._message_bus.send_message(
                user_id,
                "Aguardando Squad Lead finalizar tarefa anterior...",
                thread_id=thread_id,
            )
            await self._squad_lead_semaphore.acquire()

        try:
            return await self._run_squad_lead_inner(
                demand_id, user_id, demand_text, image_path, thread_id
            )
        finally:
            self._squad_lead_semaphore.release()

    async def _run_squad_lead_inner(
        self,
        demand_id: str,
        user_id: str,
        demand_text: str,
        image_path: str | None = None,
        thread_id: str | None = None,
    ) -> str:
        """Lógica interna do Squad Lead — protegida pelo semáforo."""
        # Expurga demandas concluídas expiradas (fire-and-forget)
        try:
            self._state_manager.cleanup_expired()
        except Exception:
            pass

        self._default_user_id = user_id
        self._default_demand_id = demand_id
        self._default_thread_id = thread_id
        self._state_manager.save_user_id(demand_id, user_id)

        # Reseta circuit breaker a cada mensagem do usuário
        self._agent_runner.reset_circuit_breaker()

        # Salva mensagem do usuario no historico
        self._conversation.save_message(
            demand_id,
            "user",
            demand_text,
        )

        full_prompt = self._build_squad_lead_prompt(demand_id, demand_text)

        # Typing enquanto Squad Lead processa
        typing_task = asyncio.create_task(self._keep_typing_and_feedback(user_id, "squad-lead"))

        self._squad_lead_busy = True
        self._squad_lead_busy_since = time.time()
        try:
            # Model routing: seleciona modelo baseado na complexidade
            selected_model = select_model(
                demand_text,
                light_model=self._light_model,
                heavy_model=self._heavy_model,
            )

            context: dict[str, Any] = {
                "demand_id": demand_id,
                "agent_name": "squad-lead",
                "fase": "coordenacao",
                "max_turns": self.SQUAD_LEAD_MAX_TURNS,
            }
            if selected_model:
                context["model_override"] = selected_model
            if image_path:
                context["image_path"] = image_path

            t0 = time.monotonic()
            resposta = await self._run_squad_lead_with_retry(
                full_prompt,
                context,
                user_id,
                thread_id,
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            model_used = selected_model or "default"
            # Registra duração (tokens serão extraídos quando o SDK expuser contagens)
            self._token_tracker.record(
                agent_name="squad-lead",
                model=model_used,
                input_tokens=0,
                output_tokens=0,
                duration_ms=duration_ms,
            )
            logger.info(
                "Squad Lead concluiu em %dms (model=%s, demand=%s)",
                duration_ms,
                model_used,
                demand_id,
            )
        finally:
            typing_task.cancel()
            self._squad_lead_busy = False

        # Envia resposta ao usuario
        if resposta:
            label = self._agent_runner.get_agent_label("squad-lead")

            # Detecta imagens/arquivos na resposta
            resposta_limpa = await self._extract_and_send_images(
                user_id,
                resposta,
            )

            # Salva resposta no historico de conversa
            self._conversation.save_message(
                demand_id,
                "assistant",
                resposta_limpa,
                agent_name="squad-lead",
            )

            # Sumariza conversa se ultrapassou threshold
            await self._maybe_summarize(demand_id)

            await self._message_bus.send_message(
                user_id,
                resposta_limpa,
                sender=label,  # type: ignore[call-arg]
                thread_id=thread_id,
            )
            # Monitor: resposta ok, reseta contador
            self._squad_lead_empty_count = 0
        else:
            self._squad_lead_empty_count += 1
            logger.warning(
                "Squad Lead resposta vazia (%d/%d) para: %s",
                self._squad_lead_empty_count,
                self._squad_lead_max_empty,
                demand_text[:80],
            )

            if self._squad_lead_empty_count >= self._squad_lead_max_empty:
                logger.warning("Squad Lead travado — resetando sessao")
                self._adapter.clear_session(demand_id)  # type: ignore[attr-defined]
                self._squad_lead_empty_count = 0
                await self._message_bus.notify(
                    user_id,
                    "Squad Lead parece travado. Sessao resetada. Tente novamente.",
                    thread_id=thread_id,
                )

        return resposta

    # Constantes de retry para o Squad Lead
    _SL_MAX_RETRIES = 2
    _SL_RETRY_BASE_DELAY = 2

    async def _run_squad_lead_with_retry(
        self,
        prompt: str,
        context: dict[str, Any],
        user_id: str,
        thread_id: str | None,
    ) -> str:
        """Executa adapter.run() para Squad Lead com retry e backoff.

        Em caso de falha definitiva, notifica o usuário diretamente.
        """
        from ai_squad.orchestrator.agent_runner import is_transient_not_timeout

        for attempt in range(self._SL_MAX_RETRIES + 1):
            try:
                return await self._adapter.run(prompt, context)
            except Exception as e:
                if not is_transient_not_timeout(e) or attempt >= self._SL_MAX_RETRIES:
                    # Falha definitiva — notifica usuário diretamente
                    logger.error(
                        "Squad Lead falhou apos %d tentativas: %s",
                        attempt + 1,
                        e,
                    )
                    is_timeout = isinstance(e, (asyncio.TimeoutError, TimeoutError))
                    if is_timeout:
                        user_msg = (
                            "⏱️ O processamento excedeu o tempo limite.\n\n"
                            "Tente simplificar a demanda ou reenvie."
                        )
                    else:
                        user_msg = (
                            f"⚠️ Erro ao processar sua demanda: {str(e)[:200]}\n\n"
                            f"Tente novamente em alguns instantes."
                        )
                    try:
                        await self._message_bus.send_message(
                            user_id,
                            user_msg,
                            thread_id=thread_id,
                        )
                    except Exception:
                        logger.error("Falha ao notificar usuario sobre erro do Squad Lead")
                    # Retorna vazio em vez de raise — run_squad_lead trata resposta vazia
                    return ""

                delay = self._SL_RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "Squad Lead erro transiente (tentativa %d/%d): %s. Retry em %ds...",
                    attempt + 1,
                    self._SL_MAX_RETRIES + 1,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)

        return ""  # Satisfaz type checker após loop de retry

    async def _trigger_squad_lead(self, event_context: str) -> None:
        """Dispara Squad Lead automaticamente (fallback com defaults)."""
        if not self._default_user_id or not self._default_demand_id:
            return

        try:
            await self.run_squad_lead(
                self._default_demand_id,
                self._default_user_id,
                event_context,
            )
        except Exception as e:
            logger.error("Erro ao disparar Squad Lead: %s", e)
            # run_squad_lead já notifica o usuário via _run_squad_lead_with_retry

    # --- Conversa direta com agente ---

    async def direct_agent_conversation(
        self,
        demand_id: str,
        user_id: str,
        agent_name: str,
        text: str,
    ) -> None:
        """Conversa direta com um agente específico (via comando)."""
        label = self._agent_runner.get_agent_label(agent_name)
        await self.notify_user(user_id, f"{label} recebeu sua mensagem...")

        resultado = await self._agent_conversation(
            demand_id,
            user_id,
            agent_name,
            text,
            {"fase": "conversa_direta", "agent_label": label},
        )

        if resultado:
            await self.notify_user(user_id, f"Conversa com {label} finalizada.")
        else:
            await self.notify_user(user_id, f"Conversa com {label} cancelada.")

    # --- Feedback background ---

    async def _keep_typing_and_feedback(
        self,
        user_id: str,
        agent_name: str,
        fase: str = "",
    ) -> None:
        """Envia typing enquanto o agente processa.

        Combina indicador de digitação com streaming de progresso real:
        a cada PROGRESS_STREAM_INTERVAL segundos, envia as últimas
        mensagens de progresso reportadas pelo agente em vez do genérico
        "Trabalhando...".
        """
        label = self._agent_runner.get_agent_label(agent_name)
        thread_id = self._resolve_thread_id(agent_name)
        elapsed = 0
        # Rastreia quantas mensagens de progresso já foram enviadas
        last_progress_sent: int = 0
        last_progress_time: float = 0.0
        try:
            while True:
                try:
                    if hasattr(self._message_bus, "send_typing"):
                        await self._message_bus.send_typing(user_id, thread_id=thread_id)
                except Exception:
                    pass
                await asyncio.sleep(self.TYPING_INTERVAL)
                elapsed += self.TYPING_INTERVAL

                # Verifica se há progresso real para enviar
                now = time.time()
                running = self._running_agents.get(agent_name)
                progress_log = running.progress_log if running else []
                new_count = len(progress_log)
                has_new_progress = new_count > last_progress_sent
                interval_ok = (now - last_progress_time) >= self.PROGRESS_STREAM_INTERVAL

                if has_new_progress and interval_ok:
                    # Envia as últimas N mensagens de progresso
                    recent = progress_log[-self.PROGRESS_STREAM_COUNT :]
                    msg = "\n".join(f"• {m}" for m in recent)
                    try:
                        await self._message_bus.send_message(
                            user_id,
                            msg,
                            sender=label,  # type: ignore[call-arg]
                            thread_id=thread_id,
                        )
                    except Exception:
                        pass
                    last_progress_sent = new_count
                    last_progress_time = now
                elif elapsed > 0 and elapsed % self.FEEDBACK_INTERVAL == 0:
                    # Fallback genérico quando não há progresso novo
                    tempo = self._format_elapsed(elapsed)
                    try:
                        await self._message_bus.send_message(
                            user_id,
                            f"Trabalhando... ({tempo})",
                            sender=label,  # type: ignore[call-arg]
                            thread_id=thread_id,
                        )
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass

    # --- Messaging ---

    async def _handle_human_needed(self, question: str) -> str:
        """Roteia pedido de decisão humana ao barramento."""
        resposta = await self._message_bus.send_approval_request(
            user_id=self._default_user_id or "default",
            question=question,
            options=["Aprovar", "Rejeitar"],
        )
        return resposta

    async def request_approval(
        self,
        demand_id: str,
        user_id: str,
        question: str,
        options: list[str],
    ) -> str:
        """Solicita aprovação humana via barramento."""
        resposta = await self._message_bus.send_approval_request(
            user_id=user_id,
            question=question,
            options=options,
        )
        return resposta

    async def notify_user(self, user_id: str, message: str) -> None:
        """Envia notificação ao usuário via barramento."""
        await self._message_bus.notify(user_id, message)

    async def dispatch_agent(
        self, demand_id: str, agent_name: str, prompt: str, context: dict[str, Any]
    ) -> str:
        """Despacha agente para execucao via adapter."""
        context["demand_id"] = demand_id
        context["agent_name"] = agent_name
        logger.info("[%s] Enviando prompt (%d chars) ao adapter...", agent_name, len(prompt))

        workspace_context = self._context_collector.collect()
        if workspace_context:
            context["workspace_context"] = workspace_context

        resultado = await self._adapter.run(prompt, context)
        logger.info("[%s] Resposta recebida (%d chars)", agent_name, len(resultado))
        return resultado

    # --- Agent conversation (usado por agentes worker e conversa direta) ---

    async def _agent_conversation(
        self,
        demand_id: str,
        user_id: str,
        agent_name: str,
        initial_prompt: str,
        context: dict[str, Any],
    ) -> str:
        """Conversa fluida entre agente e usuário.

        Loop simples: agente responde, envia ao usuario, aguarda reply.
        Apos MAX_CONVERSATIONAL_TURNS turnos, pergunta se deseja finalizar.

        Retorna resultado final ou string vazia se cancelado.
        """
        agent_label = self._agent_runner.get_agent_label(agent_name)

        self._default_user_id = user_id

        history = self._conversation.format_history_for_prompt(demand_id)
        if history:
            historico = f"{history}\n\n## Nova interação\n{initial_prompt}"
        else:
            historico = initial_prompt

        turno = 0
        while True:
            turno += 1

            typing_task = asyncio.create_task(self._keep_typing_and_feedback(user_id, agent_name))
            try:
                resposta_agente = await self.dispatch_agent(
                    demand_id,
                    agent_name,
                    historico,
                    dict(context),
                )
            finally:
                typing_task.cancel()

            self._conversation.save_message(
                demand_id,
                "agent",
                resposta_agente,
                agent_name,
            )

            await self._message_bus.send_message(
                user_id,
                resposta_agente,
                sender=agent_label,  # type: ignore[call-arg]
            )

            if turno >= self.MAX_CONVERSATIONAL_TURNS:
                finalizar = await self.request_approval(
                    demand_id,
                    user_id,
                    f"[{agent_label}] Conversa longa. Deseja finalizar?",
                    ["Finalizar", "Continuar"],
                )
                if finalizar == "Finalizar":
                    return resposta_agente
                turno = 0

            feedback = await self._message_bus.ask_user(user_id, "")
            self._conversation.save_message(demand_id, "user", feedback)

            historico = (
                f"{historico}\n\n"
                f"--- Resposta do agente ---\n{resposta_agente}\n\n"
                f"--- Resposta do usuário ---\n{feedback}"
            )
