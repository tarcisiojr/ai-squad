"""Motor de orquestração — runtime para o Squad Lead com delegação async."""

import asyncio
import logging
import subprocess
import time
from pathlib import Path
from typing import Callable

from src.models import DemandState, VALID_TRANSITIONS, AgentStatus
from src.adapters.interface import AIAgentAdapter
from src.barramento.interface import MessageBus
from src.orchestrator.context import ProductContextCollector
from src.orchestrator.conversation import ConversationStore
from src.orchestrator.daily_notes import DailyNotes
from src.orchestrator.journal import JournalStore
from src.orchestrator.lessons import LessonsStore
from src.orchestrator.model_router import select_model
from src.orchestrator.state import StateManager
from src.orchestrator.tools import (
    AgentResult, DemandStatus, RunningAgent, VerificationResult, check_workspace,
)

import re

logger = logging.getLogger("ai-dev-team.engine")


class InvalidTransitionError(Exception):
    """Erro para transições de estado inválidas."""

    pass


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
        return re.sub(r'---\w+---', '', text).strip()

    def _read_agents_md(self, agent_name: str) -> str:
        """Le o AGENTS.md de um agente."""
        path = self._agents_dir / agent_name / "AGENTS.md"
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    def _get_agents_summary(self) -> str:
        """Gera resumo de todos os agentes para o prompt do Squad Lead."""
        lines = ["## Agentes disponiveis\n"]

        for agent_id, config in self._personas.items():
            agents_md = self._read_agents_md(agent_id)

            dominio = ""
            quando = ""
            criterios = ""
            current_section = ""

            for line in agents_md.splitlines():
                if line.startswith("## Dominio"):
                    current_section = "dominio"
                elif line.startswith("## Quando Envolver"):
                    current_section = "quando"
                elif line.startswith("## Criterios de Aceite"):
                    current_section = "criterios"
                elif line.startswith("## "):
                    current_section = ""
                elif current_section == "dominio" and line.strip():
                    dominio += line.strip() + " "
                elif current_section == "quando" and line.strip():
                    quando += line + "\n"
                elif current_section == "criterios" and line.strip():
                    criterios += line + "\n"

            lines.append(f"### {config.avatar} {config.name} ({agent_id})")
            if dominio:
                lines.append(f"Dominio: {dominio.strip()}")
            if quando:
                lines.append(f"Quando envolver:\n{quando.strip()}")
            if criterios:
                lines.append(f"Criterios de aceite:\n{criterios.strip()}")
            if hasattr(config, "submodules") and config.submodules:
                subs = ", ".join(
                    f"{s.path}" + (f" ({s.description})" if s.description else "")
                    for s in config.submodules
                )
                lines.append(f"Submodulos: {subs}")
            lines.append("")

        return "\n".join(lines)

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

    # --- State machine ---

    def transition(self, demand_id: str, new_state: DemandState) -> None:
        """Realiza transição de estado para uma demanda."""
        current = self._state_manager.get_state(demand_id)

        if new_state not in VALID_TRANSITIONS.get(current, []):
            raise InvalidTransitionError(
                f"Transição inválida: {current.value} → {new_state.value}. "
                f"Transições válidas: {[s.value for s in VALID_TRANSITIONS.get(current, [])]}"
            )

        self._state_manager.set_state(demand_id, new_state)

    def get_state(self, demand_id: str) -> DemandState:
        """Retorna o estado atual de uma demanda."""
        return self._state_manager.get_state(demand_id)

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
                user_id, message, sender=label,
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
                demand_id, f"delegated_to_{agent_name}", task_description,
            )
            self._journal.set_next_expected(
                demand_id, f"{agent_name}_completion", agent_name,
                f"{label} executando: {task_description[:100]}",
            )

        # Inicia agente em background
        self._start_agent_background(
            agent_name, task_description, demand_id, user_id,
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
        self, category: str, problem: str, solution: str,
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
        """Detecta caminhos de imagem e arquivos .md na resposta e envia via Telegram.

        Procura por:
        - Markdown images: ![alt](path)
        - Caminhos absolutos de imagem: /tmp/screenshot.png
        - Markdown links para .md: [titulo](path.md)
        - Caminhos soltos de .md: /workspace/openspec/changes/spec.md
        Retorna texto limpo.
        """
        import os

        cleaned = text
        sent_files = set()

        # 1. Detecta markdown images: ![caption](path)
        if hasattr(self._message_bus, "send_photo"):
            md_img_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
            for match in md_img_pattern.finditer(text):
                caption = match.group(1)
                path = match.group(2)
                if os.path.isfile(path) and path not in sent_files:
                    try:
                        await self._message_bus.send_photo(user_id, path, caption)
                        sent_files.add(path)
                        logger.info("Imagem enviada: %s", path)
                    except Exception as e:
                        logger.error("Erro ao enviar imagem %s: %s", path, e)
                cleaned = cleaned.replace(match.group(0), "")

        # 2. Detecta caminhos soltos de imagem
        if hasattr(self._message_bus, "send_photo"):
            img_pattern = re.compile(r'(/[\w/.-]+\.(?:png|jpg|jpeg|gif|webp))', re.IGNORECASE)
            for match in img_pattern.finditer(cleaned):
                path = match.group(1)
                if os.path.isfile(path) and path not in sent_files:
                    try:
                        await self._message_bus.send_photo(user_id, path, "")
                        sent_files.add(path)
                        logger.info("Imagem enviada: %s", path)
                    except Exception as e:
                        logger.error("Erro ao enviar imagem %s: %s", path, e)
                    cleaned = cleaned.replace(path, "")

        # 3. Detecta markdown links para .md: [titulo](path.md)
        md_link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+\.md)\)')
        for match in md_link_pattern.finditer(cleaned):
            title = match.group(1)
            path = match.group(2)
            if os.path.isfile(path) and path not in sent_files:
                try:
                    content = Path(path).read_text(encoding="utf-8")
                    # Trunca se muito grande (Telegram max 4096)
                    header = f"📄 {title} ({Path(path).name})\n\n"
                    max_content = 4096 - len(header) - 50
                    if len(content) > max_content:
                        content = content[:max_content] + "\n\n... (truncado)"
                    await self._message_bus.send_message(user_id, f"{header}{content}")
                    sent_files.add(path)
                    logger.info("Arquivo .md enviado: %s", path)
                except Exception as e:
                    logger.error("Erro ao enviar .md %s: %s", path, e)
                cleaned = cleaned.replace(match.group(0), title)

        # 4. Detecta caminhos soltos de .md
        md_path_pattern = re.compile(r'(/[\w/.-]+\.md)\b')
        for match in md_path_pattern.finditer(cleaned):
            path = match.group(1)
            if os.path.isfile(path) and path not in sent_files:
                try:
                    content = Path(path).read_text(encoding="utf-8")
                    name = Path(path).name
                    header = f"📄 {name}\n\n"
                    max_content = 4096 - len(header) - 50
                    if len(content) > max_content:
                        content = content[:max_content] + "\n\n... (truncado)"
                    await self._message_bus.send_message(user_id, f"{header}{content}")
                    sent_files.add(path)
                    logger.info("Arquivo .md enviado: %s", path)
                except Exception as e:
                    logger.error("Erro ao enviar .md %s: %s", path, e)

        # Limpa linhas vazias duplicadas
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
        return cleaned

    # --- Agentes em background ---

    def _start_agent_background(
        self, agent_name: str, prompt: str, demand_id: str, user_id: str,
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
                agent_name, prompt, demand_id, user_id,
            )

        task = asyncio.create_task(_run())
        running.task = task
        self._running_agents[agent_name] = running

        # Callback quando conclui
        task.add_done_callback(
            lambda t: asyncio.create_task(
                self._on_agent_done(agent_name, t)
            )
        )

        logger.info("[%s] Agente iniciado em background (demand: %s)", agent_name, demand_id)

    async def _run_agent_work(
        self, agent_name: str, prompt: str, demand_id: str, user_id: str,
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
        typing_task = asyncio.create_task(
            self._keep_typing_and_feedback(user_id, agent_name)
        )

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
                    agent_name, f"Concluiu com sucesso ({running.elapsed_str()})",
                )

                # Registra no journal
                if running.demand_id:
                    self._journal.add_decision(
                        running.demand_id, f"{agent_name}_completed",
                        f"Verificacao: {verification.details}",
                    )

                preview = self._strip_markers(resultado)
                if len(preview) > 2000:
                    preview = preview[:2000] + "..."

                # Salva resultado do agente no historico de conversa
                if running.demand_id:
                    self._conversation.save_message(
                        running.demand_id, "assistant",
                        f"{agent_name} concluiu: {preview[:500]}",
                        agent_name=agent_name,
                    )

                await self._message_bus.send_message(
                    user_id, f"Concluido!\n\n{preview}", sender=label,
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
                    agent_name, running.retries, self.MAX_RETRIES, verification.details,
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
                    agent_name, feedback_prompt, running,
                )
                return  # Nao dispara Squad Lead ainda

            else:
                # MAX_RETRIES atingido — marca como incomplete
                running.status = "incomplete"
                logger.warning(
                    "[%s] Verificacao falhou apos %d tentativas: %s",
                    agent_name, self.MAX_RETRIES + 1, verification.details,
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
                agent_name, f"Erro: {str(e)[:100]}",
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
                user_id, f"Erro: {e}", sender=label,
            )

            await self._trigger_squad_lead_for_agent(
                running,
                f"O agente {label} falhou com erro: {e}. Decida o que fazer.",
            )

    def _start_agent_retry(
        self, agent_name: str, prompt: str, running: RunningAgent,
    ) -> None:
        """Re-invoca agente apos falha na verificacao."""
        async def _run() -> str:
            return await self._run_agent_work(
                agent_name, prompt, running.demand_id, running.user_id,
            )

        task = asyncio.create_task(_run())
        running.task = task

        task.add_done_callback(
            lambda t: asyncio.create_task(
                self._on_agent_done(agent_name, t)
            )
        )

    def _classify_agent_role(self, agent_name: str) -> str:
        """Classifica o papel de um agente baseado no AGENTS.md e config.

        Retorna: 'spec' (gera artefatos openspec), 'dev' (implementa codigo),
                 'review' (revisa resultado como texto), 'generic' (sem verificacao especifica).
        """
        persona = self._personas.get(agent_name)

        # Verifica palavras-chave no AGENTS.md
        agents_md = self._read_agents_md(agent_name).lower()

        if "openspec" in agents_md and ("proposal" in agents_md or "specs" in agents_md):
            return "spec"
        if "tasks.md" in agents_md and ("implemente" in agents_md or "codigo" in agents_md or "commit" in agents_md):
            return "dev"
        if "aprovado" in agents_md and ("rejeitado" in agents_md or "review" in agents_md or "validar" in agents_md):
            return "review"

        return "generic"

    def _verify_completion(
        self, agent_name: str, resultado: str,
    ) -> VerificationResult:
        """Verifica conclusão via artefatos reais (artifact-based, sem markers).

        Classificacao dinamica: detecta o papel do agente pelo AGENTS.md
        em vez de hardcodar nomes.
        """
        role = self._classify_agent_role(agent_name)
        issues = []

        if role == "spec":
            issues = self._verify_spec_completion()
        elif role == "dev":
            issues = self._verify_dev_completion()
        elif role == "review":
            issues = self._verify_review_completion(resultado)

        # Agentes 'generic' passam sem verificacao especifica

        if issues:
            return VerificationResult(
                passed=False,
                details="; ".join(issues),
            )

        return VerificationResult(
            passed=True,
            details="Todas as verificacoes passaram",
        )

    # Tamanho minimo em bytes para considerar um artefato valido
    MIN_ARTIFACT_SIZE = 50

    def _verify_spec_completion(self) -> list[str]:
        """Verifica artefatos openspec — dinamico, sem hardcode de agente."""
        issues = []
        ws = Path(self._workspace)
        changes_dir = ws / "openspec" / "changes"

        if not changes_dir.exists():
            return ["Diretorio openspec/changes nao encontrado"]

        active_changes = [
            d for d in changes_dir.iterdir()
            if d.is_dir() and d.name != "archive"
        ]
        if not active_changes:
            return ["Nenhuma change ativa encontrada"]

        change_dir = active_changes[-1]

        # Verifica artefatos obrigatorios com conteudo minimo
        required = ["proposal.md", "design.md", "tasks.md"]
        for filename in required:
            filepath = change_dir / filename
            if not filepath.exists():
                issues.append(f"{filename} nao encontrado")
            else:
                try:
                    size = filepath.stat().st_size
                    if size < self.MIN_ARTIFACT_SIZE:
                        issues.append(f"{filename} parece vazio ({size} bytes)")
                except OSError:
                    issues.append(f"{filename} nao pode ser lido")

        # Verifica specs com conteudo
        specs_dir = change_dir / "specs"
        if not specs_dir.exists() or not list(specs_dir.rglob("*.md")):
            issues.append("Nenhuma spec encontrada em specs/")
        else:
            for spec_file in specs_dir.rglob("*.md"):
                try:
                    content = spec_file.read_text(encoding="utf-8")
                    if len(content) < self.MIN_ARTIFACT_SIZE:
                        issues.append(
                            f"specs/{spec_file.relative_to(specs_dir)} parece vazio"
                        )
                except (OSError, UnicodeDecodeError):
                    pass

        # Verifica tasks.md tem itens suficientes
        tasks_file = change_dir / "tasks.md"
        if tasks_file.exists():
            try:
                content = tasks_file.read_text(encoding="utf-8")
                items = len(re.findall(r"- \[[ x]\]", content))
                if items < 3:
                    issues.append(f"tasks.md tem apenas {items} itens (minimo 3)")
            except (OSError, UnicodeDecodeError):
                pass

        return issues

    def _verify_dev_completion(self) -> list[str]:
        """Verifica se Dev concluiu.

        Quando ha multiplos devs (backend + frontend), cada um marca apenas
        suas tasks. A verificacao completa de tasks.md acontece no Code Review.
        Aqui verifica apenas se o agente produziu resultado (nao retornou vazio).
        """
        # Se ha outro dev rodando em paralelo, nao verifica tasks.md
        # (a verificacao completa sera no code-review)
        dev_agents_running = [
            name for name, ra in self._running_agents.items()
            if ra.status == "running" and self._classify_agent_role(name) == "dev"
        ]
        if dev_agents_running:
            # Outro dev ainda rodando — aceita conclusao parcial
            return []

        # Dev unico: verifica tasks.md
        issues = []
        tasks_check = self._check_tasks_md_completion()
        if tasks_check:
            issues.append(tasks_check)
        return issues

    def _verify_review_completion(self, resultado: str) -> list[str]:
        """Verifica se agente de revisao concluiu: report com APROVADO ou REJEITADO."""
        issues = []
        resultado_lower = resultado.lower()
        has_verdict = any(
            word in resultado_lower
            for word in ("aprovado", "approved", "rejeitado", "rejected")
        )
        if not has_verdict:
            issues.append("Resultado nao contem veredicto ('APROVADO' ou 'REJEITADO')")
        return issues

    def _check_tasks_md_completion(self) -> str | None:
        """Verifica se tasks.md tem items pendentes. Retorna descricao do problema ou None."""
        ws = Path(self._workspace)
        # Procura tasks.md em openspec/changes/*/tasks.md
        changes_dir = ws / "openspec" / "changes"
        if not changes_dir.exists():
            return None

        for change_dir in changes_dir.iterdir():
            if not change_dir.is_dir() or change_dir.name == "archive":
                continue
            tasks_file = change_dir / "tasks.md"
            if not tasks_file.exists():
                continue
            try:
                content = tasks_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            pending = len(re.findall(r"- \[ \]", content))
            done = len(re.findall(r"- \[x\]", content))
            total = pending + done

            if pending > 0:
                return f"tasks.md ({change_dir.name}): {pending}/{total} tasks pendentes"

        return None

    async def _trigger_squad_lead_for_agent(
        self, running: RunningAgent, event_context: str,
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
        if not self._running_agents:
            return "Nenhum agente ativo no momento."

        lines = []
        for name, ra in self._running_agents.items():
            label = self._get_agent_label(name)
            elapsed = ra.elapsed_str()

            if ra.status == "running":
                lines.append(f"- {label}: rodando ({elapsed})")
            elif ra.status == "done":
                preview = (ra.result or "")[:100]
                if preview:
                    preview = f" — {preview}..."
                lines.append(f"- {label}: concluido ({elapsed}){preview}")
            elif ra.status == "error":
                lines.append(f"- {label}: erro ({elapsed}) — {ra.error}")

        return "\n".join(lines)

    def _check_artifacts_enriched(self, change_name: str) -> str:
        """Verifica artefatos openspec com validação de qualidade (Criteria Gate)."""
        ws = Path(self._workspace)
        change_dir = ws / "openspec" / "changes" / change_name

        if not change_dir.exists():
            return f"Change '{change_name}' nao encontrada."

        checks = []

        # Verifica proposal
        proposal = change_dir / "proposal.md"
        checks.append({
            "name": "proposal_exists",
            "passed": proposal.exists(),
            "detail": "proposal.md encontrado" if proposal.exists() else "proposal.md ausente",
        })

        # Verifica specs com critérios de aceite
        specs_dir = change_dir / "specs"
        spec_files = list(specs_dir.rglob("*.md")) if specs_dir.exists() else []
        checks.append({
            "name": "specs_exist",
            "passed": len(spec_files) > 0,
            "detail": f"{len(spec_files)} spec(s) encontrada(s)" if spec_files else "Nenhuma spec encontrada",
        })

        for spec_file in spec_files:
            try:
                content = spec_file.read_text(encoding="utf-8")
                has_criteria = "- [ ]" in content or "- [x]" in content
                rel_path = spec_file.relative_to(specs_dir)
                checks.append({
                    "name": f"spec_criteria_{rel_path}",
                    "passed": has_criteria,
                    "detail": (
                        f"specs/{rel_path} tem criterios de aceite" if has_criteria
                        else f"specs/{rel_path} NAO tem criterios de aceite (adicione checklist '- [ ]')"
                    ),
                })
            except (OSError, UnicodeDecodeError):
                pass

        # Verifica design
        design = change_dir / "design.md"
        checks.append({
            "name": "design_exists",
            "passed": design.exists(),
            "detail": "design.md encontrado" if design.exists() else "design.md ausente",
        })

        # Verifica tasks com mínimo de itens
        tasks_file = change_dir / "tasks.md"
        if tasks_file.exists():
            try:
                content = tasks_file.read_text(encoding="utf-8")
                pending = len(re.findall(r"- \[ \]", content))
                done = len(re.findall(r"- \[x\]", content))
                total = pending + done
                checks.append({
                    "name": "tasks_minimum",
                    "passed": total >= 3,
                    "detail": f"tasks.md tem {total} itens ({done} concluidos, {pending} pendentes)"
                             if total >= 3 else f"tasks.md tem apenas {total} itens (minimo 3)",
                })
            except (OSError, UnicodeDecodeError):
                checks.append({
                    "name": "tasks_minimum",
                    "passed": False,
                    "detail": "Erro ao ler tasks.md",
                })
        else:
            checks.append({
                "name": "tasks_exists",
                "passed": False,
                "detail": "tasks.md ausente",
            })

        # Formata resultado
        passed = all(c["passed"] for c in checks)
        total_checks = len(checks)
        passed_checks = sum(1 for c in checks if c["passed"])

        lines = [f"Verificacao de artefatos: {change_name}"]
        lines.append(f"Resultado: {'APROVADO' if passed else 'REPROVADO'} ({passed_checks}/{total_checks})")
        lines.append("")
        for c in checks:
            status = "OK" if c["passed"] else "FALHA"
            lines.append(f"  [{status}] {c['detail']}")

        if not passed:
            failed = [c for c in checks if not c["passed"]]
            lines.append("")
            lines.append("Acao necessaria:")
            for c in failed:
                lines.append(f"  - Corrigir: {c['detail']}")

        return "\n".join(lines)

    def _get_demand_state_summary(self) -> str:
        """Retorna resumo do estado de todas as demandas ativas."""
        # Mapeamento estado → descrição
        state_descriptions = {
            "idle": "Aguardando inicio",
            "po_working": "PO especificando demanda",
            "awaiting_plan_approval": "Esperando aprovacao do plano pelo usuario",
            "dev_working": "Dev implementando",
            "awaiting_pr_approval": "Esperando aprovacao do PR pelo usuario",
            "ci_running": "CI rodando testes",
            "qa_validating": "QA validando implementacao",
            "done": "Concluida",
        }

        # Mapeamento estado → próxima ação
        next_actions = {
            "po_working": "Aguardar PO concluir especificacao",
            "awaiting_plan_approval": "Usuario aprovar ou rejeitar o plano",
            "dev_working": "Aguardar Dev concluir implementacao",
            "awaiting_pr_approval": "Usuario aprovar ou rejeitar o PR",
            "ci_running": "Aguardar CI passar",
            "qa_validating": "Aguardar QA concluir validacao",
        }

        # Coleta journals ativos
        active_journals = self._journal.get_active_journals()

        if not active_journals:
            # Fallback: verifica state manager
            try:
                pending = self._state_manager.get_pending_demands()
                if not pending:
                    return "Nenhuma demanda ativa."
                lines = ["Demandas ativas (sem journal):"]
                for d in pending:
                    state = d.get("state", "?")
                    lines.append(f"  - {d['demand_id']}: {state}")
                return "\n".join(lines)
            except Exception:
                return "Nenhuma demanda ativa."

        lines = [f"{len(active_journals)} demanda(s) ativa(s):\n"]
        for j in active_journals:
            demand_id = j.get("demand_id", "?")
            demand_text = j.get("demand_text", "?")
            phase = j.get("current_phase", "?")
            description = state_descriptions.get(phase, phase)
            next_action = next_actions.get(phase, "Avaliar proximo passo")
            next_expected = j.get("next_expected")

            lines.append(f"### {demand_id}")
            lines.append(f"  Demanda: {demand_text}")
            lines.append(f"  Fase: {phase} ({description})")
            lines.append(f"  Proxima acao: {next_action}")
            if next_expected:
                lines.append(f"  Detalhe: {next_expected.get('description', '')}")

            # Verifica se tem agente rodando
            running = [
                ra for ra in self._running_agents.values()
                if ra.demand_id == demand_id and ra.status == "running"
            ]
            if running:
                for ra in running:
                    label = self._get_agent_label(ra.agent_name)
                    lines.append(f"  Agente ativo: {label} ({ra.elapsed_str()})")
            lines.append("")

        return "\n".join(lines)

    # --- Squad Lead (chamadas curtas) ---

    async def run_squad_lead(
        self, demand_id: str, user_id: str, demand_text: str,
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

        # Contexto do produto
        product_context = self._context_collector.collect()
        if product_context:
            prompt_parts.append(f"## Contexto do Projeto\n\n{product_context}")

        # Salva mensagem do usuario no historico
        self._conversation.save_message(
            demand_id, "user", demand_text,
        )

        prompt_parts.append(f"## Mensagem do usuario\n\n{demand_text}")

        full_prompt = "\n\n".join(prompt_parts)

        # Typing enquanto Squad Lead processa
        typing_task = asyncio.create_task(
            self._keep_typing_and_feedback(user_id, "squad-lead")
        )

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
                user_id, resposta_limpa,
            )

            # Salva resposta no historico de conversa
            self._conversation.save_message(
                demand_id, "assistant", resposta_limpa, agent_name="squad-lead",
            )

            # Sumariza conversa se ultrapassou threshold
            await self._maybe_summarize(demand_id)

            await self._message_bus.send_message(
                user_id, resposta_limpa, sender=label,
            )
            # Monitor: resposta ok, reseta contador
            self._squad_lead_empty_count = 0
        else:
            self._squad_lead_empty_count += 1
            logger.warning(
                "Squad Lead resposta vazia (%d/%d) para: %s",
                self._squad_lead_empty_count, self._squad_lead_max_empty,
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

    async def run_demand_cycle(
        self, demand_id: str, user_id: str, demand_text: str,
    ) -> None:
        """Executa demanda via Squad Lead."""
        await self.run_squad_lead(demand_id, user_id, demand_text)

    # --- Conversa direta com agente ---

    async def direct_agent_conversation(
        self, demand_id: str, user_id: str, agent_name: str, text: str,
    ) -> None:
        """Conversa direta com um agente específico (via comando)."""
        label = self._get_agent_label(agent_name)
        await self.notify_user(user_id, f"{label} recebeu sua mensagem...")

        resultado = await self._agent_conversation(
            demand_id, user_id, agent_name, text,
            {"fase": "conversa_direta", "agent_label": label},
        )

        if resultado:
            await self.notify_user(user_id, f"Conversa com {label} finalizada.")
        else:
            await self.notify_user(user_id, f"Conversa com {label} cancelada.")

    # --- Feedback background ---

    async def _keep_typing_and_feedback(
        self, user_id: str, agent_name: str, fase: str = "",
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
                            user_id, f"Trabalhando... ({tempo})", sender=label,
                        )
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass

    # --- Messaging ---

    async def _handle_human_needed(self, question: str) -> str:
        """Roteia pedido de decisão humana ao barramento."""
        resposta = await self._message_bus.send_approval_request(
            user_id="default",
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
        self, demand_id: str, user_id: str, agent_name: str,
        initial_prompt: str, context: dict,
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

            typing_task = asyncio.create_task(
                self._keep_typing_and_feedback(user_id, agent_name)
            )
            try:
                resposta_agente = await self.dispatch_agent(
                    demand_id, agent_name, historico, dict(context),
                )
            finally:
                typing_task.cancel()

            self._conversation.save_message(
                demand_id, "agent", resposta_agente, agent_name,
            )

            has_marker = done_marker and done_marker in resposta_agente

            if has_marker:
                texto_limpo = resposta_agente.replace(done_marker, "").strip()

                aprovacao = await self.request_approval(
                    demand_id, user_id,
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
                user_id, self._strip_markers(resposta_agente), sender=agent_label,
            )

            if turno >= self.MAX_TURNS_WITHOUT_MARKER:
                finalizar = await self.request_approval(
                    demand_id, user_id,
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

    # --- Metodos legados (compatibilidade) ---

    async def _invoke_agent(
        self, demand_id: str, user_id: str, agent_name: str, prompt: str,
    ) -> str:
        """Invoca um agente — compatibilidade."""
        if agent_name not in self._personas:
            available = ", ".join(self._personas.keys())
            return f"Agente '{agent_name}' nao encontrado. Disponiveis: {available}"

        label = self._get_agent_label(agent_name)
        await self.notify_user(user_id, f"{label} iniciando...")

        agents_md = self._read_agents_md(agent_name)
        context = {
            "fase": "execucao",
            "system_instructions": agents_md,
        }

        specs_dir = Path(self._workspace) / "specs" / demand_id
        specs_dir.mkdir(parents=True, exist_ok=True)

        resultado = await self._agent_conversation(
            demand_id, user_id, agent_name, prompt, context,
        )

        status = self._demand_statuses.get(demand_id)
        if status:
            status.set_result(agent_name, AgentResult(
                agent_name=agent_name,
                result=resultado,
                success=bool(resultado),
            ))

        return resultado or "(agente cancelado pelo usuario)"

    async def _invoke_parallel(
        self, demand_id: str, user_id: str,
        agents: list[str], prompts: list[str],
    ) -> list[str]:
        """Invoca multiplos agentes em paralelo — compatibilidade."""
        tasks = [
            self._invoke_agent(demand_id, user_id, agent, prompt)
            for agent, prompt in zip(agents, prompts)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            str(r) if isinstance(r, Exception) else r
            for r in results
        ]
