"""Motor de orquestração — runtime para o Squad Lead com delegação async."""

import asyncio
import logging
import re
import time
from pathlib import Path

from src.adapters.interface import AIAgentAdapter
from src.barramento.interface import MessageBus
from src.orchestrator.context import ProductContextCollector
from src.orchestrator.conversation import ConversationStore
from src.orchestrator.daily_notes import DailyNotes
from src.orchestrator.journal import JournalStore
from src.orchestrator.lessons import LessonsStore
from src.orchestrator.media import extract_and_send_media
from src.orchestrator.model_router import select_model
from src.orchestrator.pipeline import PipelineLoader
from src.orchestrator.pipeline_state import PipelineExecutor
from src.orchestrator.prompt_builder import (
    get_agents_summary,
    get_demand_state_summary,
    get_running_agents_status,
    read_agents_md,
)
from src.orchestrator.state import StateManager
from src.orchestrator.tools import (
    DemandStatus,
    RunningAgent,
    VerificationResult,
)
from src.orchestrator.verification import (
    check_artifacts_enriched,
    classify_agent_role,
    verify_completion,
)

logger = logging.getLogger("ai-dev-team.engine")


class OrchestrationEngine:
    """Motor de orquestração com delegação async.

    O Squad Lead usa chamadas SDK curtas (max_turns=5) e delega trabalho
    a agentes via MCP tools. Agentes rodam em background como asyncio tasks.
    """

    # Intervalo em segundos para reenviar "digitando..."
    TYPING_INTERVAL = 4
    # Intervalo em segundos para feedback periodico
    FEEDBACK_INTERVAL = 30
    # Limite de turnos sem marcador antes de perguntar ao usuario
    MAX_TURNS_WITHOUT_MARKER = 10
    # max_turns para o Squad Lead (precisa de margem para tools como Playwright + resposta)
    SQUAD_LEAD_MAX_TURNS = 15
    # Maximo de re-tentativas quando verificacao falha
    MAX_RETRIES = 2

    # Intervalo em segundos para enviar feedback de tempo ao usuario
    # O agente envia report_progress com detalhes reais do que esta fazendo.
    # Este feedback e apenas um indicador de que ainda esta rodando.
    FEEDBACK_TIME_ONLY = True

    def __init__(
        self,
        adapter: AIAgentAdapter,
        message_bus: MessageBus,
        state_manager: StateManager,
        workspace: str = "/workspace",
        personas: dict | None = None,
        agents_dir: str = "/app/agents",
        agent_timeout: int = 300,
        dev_timeout: int = 600,
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
        self._dev_timeout = dev_timeout
        self._light_model = light_model
        self._heavy_model = heavy_model
        self._context_collector = ProductContextCollector(workspace)
        self._conversation = ConversationStore(state_manager._state_dir)
        self._journal = JournalStore(state_dir=state_manager._state_dir)
        self._lessons = LessonsStore(state_dir=state_manager._state_dir)
        self._daily_notes = DailyNotes(state_dir=state_manager._state_dir)
        self._demand_statuses: dict[str, DemandStatus] = {}

        # Pipeline declarativo (opcional — modo legado se não configurado)
        self._pipeline_executor: PipelineExecutor | None = None
        if pipeline_dir:
            loader = PipelineLoader(pipeline_dir)
            pipeline = loader.load()
            if pipeline:
                self._pipeline_executor = PipelineExecutor(
                    state_dir=state_manager._state_dir,
                    pipeline=pipeline,
                )
                logger.info(
                    "Pipeline carregado: %s (%d steps)",
                    pipeline.name,
                    len(pipeline.steps),
                )

        # Agentes em background: agent_name → RunningAgent
        self._running_agents: dict[str, RunningAgent] = {}

        # user_id e demand_id defaults (usados pelo Squad Lead quando nao ha agente)
        self._default_user_id: str = ""
        self._default_demand_id: str = ""

        # Monitor do Squad Lead: detecta respostas vazias consecutivas
        self._squad_lead_empty_count: int = 0
        self._squad_lead_max_empty: int = 3  # reseta sessao apos N respostas vazias

        # Registra callbacks no adapter
        self._adapter.on_human_needed(self._handle_human_needed)
        if hasattr(self._adapter, "set_progress_callback"):
            self._adapter.set_progress_callback(self._handle_progress)
        if hasattr(self._adapter, "set_start_agent_callback"):
            self._adapter.set_start_agent_callback(self._handle_start_agent)
        if hasattr(self._adapter, "set_get_agents_callback"):
            self._adapter.set_get_agents_callback(self._handle_get_agents)
        if hasattr(self._adapter, "set_check_artifacts_callback"):
            self._adapter.set_check_artifacts_callback(self._handle_check_artifacts)
        if hasattr(self._adapter, "set_get_demand_state_callback"):
            self._adapter.set_get_demand_state_callback(self._handle_get_demand_state)
        if hasattr(self._adapter, "set_read_journal_callback"):
            self._adapter.set_read_journal_callback(self._handle_read_journal)
        if hasattr(self._adapter, "set_send_image_callback"):
            self._adapter.set_send_image_callback(self._handle_send_image)
        if hasattr(self._adapter, "set_learn_lesson_callback"):
            self._adapter.set_learn_lesson_callback(self._handle_learn_lesson)
        if hasattr(self._adapter, "set_get_pipeline_state_callback"):
            self._adapter.set_get_pipeline_state_callback(self._handle_get_pipeline_state)
        if hasattr(self._adapter, "set_advance_step_callback"):
            self._adapter.set_advance_step_callback(self._handle_advance_step)
        if hasattr(self._adapter, "set_skip_step_callback"):
            self._adapter.set_skip_step_callback(self._handle_skip_step)
        if hasattr(self._adapter, "set_rerun_step_callback"):
            self._adapter.set_rerun_step_callback(self._handle_rerun_step)

        # Registra callback de sumarização no conversation store
        self._conversation.set_summarize_callback(self._summarize_via_llm)

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

    def _get_agent_label(self, agent_name: str) -> str:
        """Retorna label do agente a partir das personas da config."""
        persona = self._personas.get(agent_name)
        if persona:
            return f"{persona.avatar} {persona.name}"
        return agent_name

    def _get_agent_timeout(self, agent_name: str) -> int:
        """Retorna timeout especifico por agente.

        Prioridade: config do agente > dev_timeout (retrocompat) > agent_timeout padrao
        """
        persona = self._personas.get(agent_name)
        if persona and hasattr(persona, "timeout") and persona.timeout > 0:
            return persona.timeout
        if agent_name == "dev":
            return self._dev_timeout
        return self._agent_timeout

    def _get_done_marker(self, agent_name: str) -> str:
        """Retorna marcador de conclusão do agente."""
        persona = self._personas.get(agent_name)
        if persona and persona.done_marker:
            return persona.done_marker
        return ""

    def _strip_markers(self, text: str) -> str:
        """Remove marcadores internos (---ALGO---) do texto antes de enviar ao usuario."""
        return re.sub(r"---\w+---", "", text).strip()

    def _read_agents_md(self, agent_name: str) -> str:
        """Le o AGENTS.md de um agente."""
        return read_agents_md(agent_name, self._agents_dir)

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

    async def _handle_progress(self, agent_name: str, message: str) -> None:
        """Recebe progresso do agente (via report_progress) e envia ao usuario.

        Tolerante a falha — nunca propaga excecao para nao matar o agente.
        """
        user_id = self._resolve_user_id(agent_name)
        if not user_id:
            return
        try:
            label = self._get_agent_label(agent_name)
            await self._message_bus.send_message(
                user_id,
                message,
                sender=label,
            )
        except Exception as e:
            logger.warning("[%s] Falha ao enviar progresso: %s", agent_name, e)

    async def _handle_start_agent(self, agent_name: str, task_description: str) -> str:
        """Callback da MCP tool start_agent — inicia agente em background."""
        if agent_name not in self._personas:
            available = ", ".join(self._personas.keys())
            return f"Agente '{agent_name}' nao encontrado. Disponiveis: {available}"

        if agent_name in self._running_agents:
            ra = self._running_agents[agent_name]
            if ra.status == "running":
                return f"Agente '{agent_name}' ja esta rodando ({ra.elapsed_str()}). Aguarde conclusao."

        label = self._get_agent_label(agent_name)
        demand_id = self._default_demand_id
        user_id = self._default_user_id

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
        self._start_agent_background(
            agent_name,
            task_description,
            demand_id,
            user_id,
        )

        return f"Agente {label} iniciado em background. Voce sera notificado quando concluir."

    async def _handle_get_agents(self) -> str:
        """Callback da MCP tool get_running_agents."""
        return self._get_running_agents_status()

    async def _handle_check_artifacts(self, change_name: str) -> str:
        """Callback da MCP tool check_artifacts — validação enriquecida."""
        return self._check_artifacts_enriched(change_name)

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
                agent_name=self._adapter._current_agent_name,
                demand_id=self._default_demand_id,
            )
            logger.info("Licao registrada: [%s] %s", category, problem[:60])
        except Exception as e:
            logger.warning("Falha ao registrar licao: %s", e)

    async def _handle_send_image(self, image_path: str, caption: str = "") -> None:
        """Callback da MCP tool send_image — envia imagem ao usuario via Telegram.

        Tolerante a falha.
        """
        user_id = self._default_user_id
        if not user_id:
            return
        try:
            if hasattr(self._message_bus, "send_photo"):
                await self._message_bus.send_photo(user_id, image_path, caption)
            else:
                logger.warning("MessageBus nao suporta envio de fotos")
        except Exception as e:
            logger.warning("Falha ao enviar imagem: %s", e)

    async def _extract_and_send_images(self, user_id: str, text: str) -> str:
        """Delega detecção de imagens/arquivos ao módulo media."""
        return await extract_and_send_media(user_id, text, self._message_bus)

    # --- Pipeline tools callbacks ---

    async def _handle_get_pipeline_state(self) -> str:
        """Callback da MCP tool get_pipeline_state."""
        if not self._pipeline_executor:
            return "Pipeline nao configurado. Operando em modo legado."
        demand_id = self._default_demand_id
        if not demand_id:
            return "Nenhuma demanda ativa."
        return self._pipeline_executor.format_state_for_prompt(demand_id)

    async def _handle_advance_step(self) -> str:
        """Callback da MCP tool advance_step."""
        if not self._pipeline_executor:
            return "Pipeline nao configurado."
        demand_id = self._default_demand_id
        if not demand_id:
            return "Nenhuma demanda ativa."
        current = self._pipeline_executor.get_current_step(demand_id)
        if not current:
            return "Nenhum step ativo para avancar."
        next_step = self._pipeline_executor.complete_step(demand_id, current.id)
        if next_step:
            return f"Avancado para step: {next_step.name} ({next_step.id})"
        return "Pipeline concluido."

    async def _handle_skip_step(self, step_id: str) -> str:
        """Callback da MCP tool skip_step."""
        if not self._pipeline_executor:
            return "Pipeline nao configurado."
        demand_id = self._default_demand_id
        if not demand_id:
            return "Nenhuma demanda ativa."
        next_step = self._pipeline_executor.skip_step(demand_id, step_id)
        if next_step:
            return f"Step '{step_id}' pulado. Proximo: {next_step.name}"
        return f"Step '{step_id}' pulado. Pipeline concluido."

    async def _handle_rerun_step(self, step_id: str) -> str:
        """Callback da MCP tool rerun_step."""
        if not self._pipeline_executor:
            return "Pipeline nao configurado."
        demand_id = self._default_demand_id
        if not demand_id:
            return "Nenhuma demanda ativa."
        ok = self._pipeline_executor.rerun_step(demand_id, step_id)
        if ok:
            return f"Step '{step_id}' re-iniciado."
        return f"Step '{step_id}' nao encontrado."

    # --- Agentes em background ---

    def _start_agent_background(
        self,
        agent_name: str,
        prompt: str,
        demand_id: str,
        user_id: str,
    ) -> None:
        """Inicia agente como asyncio task em background."""
        running = RunningAgent(
            agent_name=agent_name,
            demand_id=demand_id,
            user_id=user_id,
            started_at=time.time(),
            status="running",
        )

        async def _run() -> str:
            return await self._run_agent_work(
                agent_name,
                prompt,
                demand_id,
                user_id,
            )

        task = asyncio.create_task(_run())
        running.task = task
        self._running_agents[agent_name] = running

        # Callback quando conclui
        task.add_done_callback(lambda t: asyncio.create_task(self._on_agent_done(agent_name, t)))

        logger.info("[%s] Agente iniciado em background (demand: %s)", agent_name, demand_id)

    async def _run_agent_work(
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

        context = {
            "demand_id": demand_id,
            "agent_name": agent_name,
            "fase": "execucao",
            "system_instructions": agents_md,
            "timeout": timeout,
        }
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
            context["product_context"] = "\n\n".join(context_parts)

        # Cria diretorio de specs
        specs_dir = Path(self._workspace) / "specs" / demand_id
        specs_dir.mkdir(parents=True, exist_ok=True)

        # Inicia typing + feedback background para este agente
        typing_task = asyncio.create_task(self._keep_typing_and_feedback(user_id, agent_name))

        try:
            resultado = await self._adapter.run(prompt, context)
        finally:
            typing_task.cancel()

        return resultado

    async def _on_agent_done(self, agent_name: str, task: asyncio.Task) -> None:
        """Callback quando agente background conclui — com verification loop."""
        running = self._running_agents.get(agent_name)
        if not running:
            return

        label = self._get_agent_label(agent_name)
        user_id = running.user_id

        try:
            resultado = task.result()
            running.result = resultado
            logger.info("[%s] Agente retornou resultado em background", agent_name)

            # Verification loop (Ralph pattern)
            verification = self._verify_completion(agent_name, resultado)

            if verification.passed:
                running.status = "done"
                logger.info("[%s] Verificacao passou: %s", agent_name, verification.details)

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
                        f"Verificacao: {verification.details}",
                    )

                preview = self._strip_markers(resultado)
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
                    sender=label,
                )

                # Dispara Squad Lead com contexto completo
                await self._trigger_squad_lead_for_agent(
                    running,
                    f"O agente {label} concluiu com sucesso. "
                    f"Verificacao: {verification.details}. "
                    f"Decida o proximo passo.",
                )
            elif running.retries < self.MAX_RETRIES:
                # Re-invoca agente com feedback do que falta
                running.retries += 1
                running.status = "running"
                logger.info(
                    "[%s] Verificacao falhou (tentativa %d/%d): %s",
                    agent_name,
                    running.retries,
                    self.MAX_RETRIES,
                    verification.details,
                )

                await self._message_bus.send_message(
                    user_id,
                    f"Verificacao falhou: {verification.details}. "
                    f"Re-invocando (tentativa {running.retries + 1}/{self.MAX_RETRIES + 1})...",
                    sender=label,
                )

                # Re-invoca com feedback
                feedback_prompt = (
                    f"Voce reportou conclusao mas a verificacao falhou:\n"
                    f"{verification.details}\n\n"
                    f"Continue o trabalho e conclua o que falta."
                )
                self._start_agent_retry(
                    agent_name,
                    feedback_prompt,
                    running,
                )
                return  # Nao dispara Squad Lead ainda

            else:
                # MAX_RETRIES atingido — marca como incomplete
                running.status = "incomplete"
                logger.warning(
                    "[%s] Verificacao falhou apos %d tentativas: %s",
                    agent_name,
                    self.MAX_RETRIES + 1,
                    verification.details,
                )

                # Registra licao aprendida
                self._lessons.add(
                    category="retrabalho",
                    problem=f"{agent_name} falhou apos {self.MAX_RETRIES + 1} tentativas: {verification.details}",
                    solution=f"Verificar se {agent_name} recebe instrucoes claras e artefatos completos antes de iniciar",
                    agent_name=agent_name,
                    demand_id=running.demand_id,
                )

                await self._message_bus.send_message(
                    user_id,
                    f"Incompleto apos {self.MAX_RETRIES + 1} tentativas. "
                    f"Problema: {verification.details}",
                    sender=label,
                )

                await self._trigger_squad_lead_for_agent(
                    running,
                    f"O agente {label} nao conseguiu concluir apos {self.MAX_RETRIES + 1} tentativas. "
                    f"Verificacao: {verification.details}. "
                    f"Decida o que fazer.",
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
                sender=label,
            )

            await self._trigger_squad_lead_for_agent(
                running,
                f"O agente {label} falhou com erro: {e}. Decida o que fazer.",
            )

    def _start_agent_retry(
        self,
        agent_name: str,
        prompt: str,
        running: RunningAgent,
    ) -> None:
        """Re-invoca agente apos falha na verificacao."""

        async def _run() -> str:
            return await self._run_agent_work(
                agent_name,
                prompt,
                running.demand_id,
                running.user_id,
            )

        task = asyncio.create_task(_run())
        running.task = task

        task.add_done_callback(lambda t: asyncio.create_task(self._on_agent_done(agent_name, t)))

    def _classify_agent_role(self, agent_name: str) -> str:
        """Delega classificação ao módulo verification."""
        persona = self._personas.get(agent_name)
        role_override = persona.role if persona and persona.role else ""
        return classify_agent_role(agent_name, self._agents_dir, role_override)

    def _verify_completion(
        self,
        agent_name: str,
        resultado: str,
    ) -> VerificationResult:
        """Delega verificação ao módulo verification."""
        persona = self._personas.get(agent_name)
        role_override = persona.role if persona and persona.role else ""
        return verify_completion(
            agent_name,
            resultado,
            self._workspace,
            self._agents_dir,
            self._running_agents,
            role_override=role_override,
        )

    def _verify_spec_completion(self) -> list[str]:
        """Delega ao módulo verification (retrocompat para testes)."""
        from src.orchestrator.verification import _verify_spec_completion

        return _verify_spec_completion(self._workspace)

    async def _trigger_squad_lead_for_agent(
        self,
        running: RunningAgent,
        event_context: str,
    ) -> None:
        """Dispara Squad Lead com contexto do agente que concluiu."""
        user_id = running.user_id or self._default_user_id
        demand_id = running.demand_id or self._default_demand_id

        if not user_id or not demand_id:
            return

        try:
            await self.run_squad_lead(demand_id, user_id, event_context)
        except Exception as e:
            logger.error("Erro ao disparar Squad Lead: %s", e)

    def _get_running_agents_status(self) -> str:
        """Retorna status formatado de todos os agentes."""
        return get_running_agents_status(self._running_agents, self._personas)

    def _check_artifacts_enriched(self, change_name: str) -> str:
        """Delega ao módulo verification."""
        return check_artifacts_enriched(change_name, self._workspace)

    def _check_tasks_md_completion(self) -> str | None:
        """Delega ao módulo verification (retrocompat para testes)."""
        from src.orchestrator.verification import _check_tasks_md_completion

        return _check_tasks_md_completion(self._workspace)

    def _get_demand_state_summary(self) -> str:
        """Retorna resumo do estado de todas as demandas ativas."""
        return get_demand_state_summary(
            self._journal,
            self._state_manager,
            self._running_agents,
            self._personas,
        )

    # --- Squad Lead (chamadas curtas) ---

    async def run_squad_lead(
        self,
        demand_id: str,
        user_id: str,
        demand_text: str,
    ) -> str:
        """Executa Squad Lead com chamada SDK curta.

        Retorna a resposta do Squad Lead. Nao bloqueia — se o Squad Lead
        delegar via start_agent, o agente roda em background.
        """
        self._default_user_id = user_id
        self._default_demand_id = demand_id
        self._state_manager.save_user_id(demand_id, user_id)

        # Monta prompt
        squad_md = self._read_agents_md("squad-lead")
        agents_summary = self._get_agents_summary()
        agents_status = self._get_running_agents_status()

        prompt_parts = []
        if squad_md:
            prompt_parts.append(squad_md)
        prompt_parts.append(agents_summary)

        # Injeta estado dos agentes em background
        if self._running_agents:
            prompt_parts.append(f"## Estado atual dos agentes\n\n{agents_status}")

        # Injeta estado de demandas ativas (State Awareness)
        demand_state = self._get_demand_state_summary()
        if demand_state and demand_state != "Nenhuma demanda ativa.":
            prompt_parts.append(f"## Estado das demandas\n\n{demand_state}")

        # Injeta journal (histórico de decisões)
        journal_summary = self._journal.get_active_summaries()
        if journal_summary and journal_summary != "Nenhuma demanda ativa.":
            prompt_parts.append(f"## Historico de decisoes (Journal)\n\n{journal_summary}")

        # Injeta historico de conversa (persistido entre restarts)
        conversation_history = self._conversation.format_history_for_prompt(demand_id)
        if conversation_history:
            prompt_parts.append(conversation_history)

        # Injeta licoes aprendidas (evitar erros passados)
        lessons = self._lessons.format_for_prompt(demand_text)
        if lessons:
            prompt_parts.append(lessons)

        # Injeta notas diárias (continuidade entre sessões)
        daily_notes = self._daily_notes.load_recent()
        if daily_notes:
            prompt_parts.append(daily_notes)

        # Injeta estado do pipeline (se configurado)
        if self._pipeline_executor:
            pipeline_state = self._pipeline_executor.format_state_for_prompt(demand_id)
            if pipeline_state:
                prompt_parts.append(pipeline_state)

        # Contexto do produto
        product_context = self._context_collector.collect()
        if product_context:
            prompt_parts.append(f"## Contexto do Projeto\n\n{product_context}")

        # Salva mensagem do usuario no historico
        self._conversation.save_message(
            demand_id,
            "user",
            demand_text,
        )

        prompt_parts.append(f"## Mensagem do usuario\n\n{demand_text}")

        full_prompt = "\n\n".join(prompt_parts)

        # Typing enquanto Squad Lead processa
        typing_task = asyncio.create_task(self._keep_typing_and_feedback(user_id, "squad-lead"))

        try:
            # Model routing: seleciona modelo baseado na complexidade
            selected_model = select_model(
                demand_text,
                light_model=self._light_model,
                heavy_model=self._heavy_model,
            )

            context = {
                "demand_id": demand_id,
                "agent_name": "squad-lead",
                "fase": "coordenacao",
                "max_turns": self.SQUAD_LEAD_MAX_TURNS,
            }
            if selected_model:
                context["model_override"] = selected_model

            resposta = await self._adapter.run(full_prompt, context)
        finally:
            typing_task.cancel()

        # Envia resposta ao usuario
        if resposta:
            label = self._get_agent_label("squad-lead")

            # Limpa marcadores e detecta imagens/arquivos na resposta
            resposta_limpa = self._strip_markers(resposta)
            resposta_limpa = await self._extract_and_send_images(
                user_id,
                resposta_limpa,
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
                sender=label,
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
                self._adapter.clear_session(demand_id)
                self._squad_lead_empty_count = 0
                await self._message_bus.notify(
                    user_id,
                    "Squad Lead parece travado. Sessao resetada. Tente novamente.",
                )

        return resposta

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

    # --- Conversa direta com agente ---

    async def direct_agent_conversation(
        self,
        demand_id: str,
        user_id: str,
        agent_name: str,
        text: str,
    ) -> None:
        """Conversa direta com um agente específico (via comando)."""
        label = self._get_agent_label(agent_name)
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

        O agente envia report_progress com detalhes reais do que esta fazendo.
        Este metodo apenas mantem o indicador de 'digitando...' ativo e
        envia tempo decorrido periodicamente.
        """
        label = self._get_agent_label(agent_name)
        elapsed = 0
        try:
            while True:
                try:
                    if hasattr(self._message_bus, "send_typing"):
                        await self._message_bus.send_typing(user_id)
                except Exception:
                    pass
                await asyncio.sleep(self.TYPING_INTERVAL)
                elapsed += self.TYPING_INTERVAL

                if elapsed > 0 and elapsed % self.FEEDBACK_INTERVAL == 0:
                    tempo = self._format_elapsed(elapsed)
                    try:
                        await self._message_bus.send_message(
                            user_id,
                            f"Trabalhando... ({tempo})",
                            sender=label,
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
        self, demand_id: str, agent_name: str, prompt: str, context: dict
    ) -> str:
        """Despacha agente para execucao via adapter."""
        context["demand_id"] = demand_id
        context["agent_name"] = agent_name
        logger.info("[%s] Enviando prompt (%d chars) ao adapter...", agent_name, len(prompt))

        product_context = self._context_collector.collect()
        if product_context:
            context["product_context"] = product_context

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
        context: dict,
    ) -> str:
        """Conversa fluida entre agente e usuário.

        Modo CHAT: agente responde sem marcador → texto livre ida-e-volta
        Modo APPROVAL: agente inclui marcador → botões [Aprovar] [Rejeitar]

        Retorna resultado final aprovado, ou string vazia se cancelado.
        """
        agent_label = self._get_agent_label(agent_name)
        done_marker = self._get_done_marker(agent_name)

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

            has_marker = done_marker and done_marker in resposta_agente

            if has_marker:
                texto_limpo = resposta_agente.replace(done_marker, "").strip()

                aprovacao = await self.request_approval(
                    demand_id,
                    user_id,
                    f"[{agent_label}]\n\n{texto_limpo}",
                    ["Aprovar", "Rejeitar"],
                )

                if aprovacao == "Aprovar":
                    return texto_limpo

                feedback = await self._message_bus.ask_user(
                    user_id,
                    f"[{agent_label}] O que gostaria de ajustar?",
                )
                self._conversation.save_message(demand_id, "user", feedback)
                historico = (
                    f"{historico}\n\n"
                    f"--- Resposta do agente (rejeitada) ---\n{texto_limpo}\n\n"
                    f"--- Feedback do usuário ---\n{feedback}"
                )
                turno = 0
                continue

            await self._message_bus.send_message(
                user_id,
                self._strip_markers(resposta_agente),
                sender=agent_label,
            )

            if turno >= self.MAX_TURNS_WITHOUT_MARKER:
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
