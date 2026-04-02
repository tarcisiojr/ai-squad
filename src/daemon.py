"""Daemon do ai-squad — loop infinito escutando mensageria."""

import asyncio
import logging
import os
import re
import signal
import sys
import unicodedata
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from src.path_resolver import PathResolver

from src.adapters.interface import AIAgentAdapter
from src.factory import AgentConfig, PlatformConfig, PlatformFactory, SquadLeadConfig
from src.messaging.interface import MessageBus
from src.messaging.registry import get as get_provider
from src.messaging.registry import load_builtin_providers
from src.orchestrator.engine import OrchestrationEngine
from src.orchestrator.journal import JournalStore
from src.orchestrator.state import StateManager
from src.orchestrator.thread_map import ThreadDemandMap
from src.orchestrator.thread_tracker import ThreadAction, ThreadTracker

# Configuração de logging estruturado
# No modo TUI, o logging já foi configurado para arquivo antes do import
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
logger = logging.getLogger("ai-squad.daemon")


class Daemon:
    """Processo daemon que escuta mensageria e orquestra demandas.

    Roda em loop infinito (Docker ou local foreground).
    Processa uma demanda por vez, enfileirando as demais.
    """

    def __init__(self, path_resolver: "PathResolver | None" = None) -> None:
        from src.path_resolver import PathResolver

        self._shutdown_event = asyncio.Event()
        self._engine: OrchestrationEngine | None = None
        self._bus: MessageBus | None = None
        self._adapter: AIAgentAdapter | None = None
        self._config: PlatformConfig | None = None
        self._paths = path_resolver or PathResolver("docker")
        # Conversa livre com o Squad Lead no Tópico Geral (sem pipeline)
        self._squad_lead_conversation_id = "squad-lead-session"
        self._team_name = os.environ.get("TEAM_NAME", "default")
        # Mapeamento thread_id ↔ demand_id para threads/tópicos
        self._thread_map: ThreadDemandMap | None = None
        # Rastreamento de estado do bot por thread
        self._thread_tracker: ThreadTracker | None = None

    @property
    def engine(self) -> OrchestrationEngine:
        """Acesso seguro ao engine — falha se não inicializado."""
        assert self._engine is not None, (
            "Engine não inicializado — chame _setup_components primeiro"
        )
        return self._engine

    @property
    def bus(self) -> MessageBus:
        """Acesso seguro ao message bus — falha se não inicializado."""
        assert self._bus is not None, (
            "MessageBus não inicializado — chame _setup_components primeiro"
        )
        return self._bus

    @property
    def config(self) -> PlatformConfig:
        """Acesso seguro à config — falha se não carregada."""
        assert self._config is not None, "Config não carregada — chame _load_config primeiro"
        return self._config

    def _load_config(self) -> PlatformConfig:
        """Carrega configuração de config.yaml + variáveis de ambiente."""
        # Carrega .env se existir
        env_path = self._paths.env_path
        if env_path.exists():
            load_dotenv(env_path)

        # Carrega config.yaml base
        config_path = self._paths.config_path
        if config_path.exists():
            config = PlatformConfig.from_yaml(config_path)
        else:
            config = PlatformConfig(
                ai_provider=os.environ.get("AI_PROVIDER", "claude-agent-sdk"),
                messaging_provider=os.environ.get("MESSAGING_PROVIDER", "telegram"),
            )

        # Variáveis de ambiente sobrescrevem YAML
        if os.environ.get("AI_PROVIDER"):
            config.ai_provider = os.environ["AI_PROVIDER"]
        if os.environ.get("MESSAGING_PROVIDER"):
            config.messaging_provider = os.environ["MESSAGING_PROVIDER"]
        if os.environ.get("AGENT_TIMEOUT"):
            config.agent_timeout = int(os.environ["AGENT_TIMEOUT"])
        if os.environ.get("STATE_DIR"):
            config.state_dir = os.environ["STATE_DIR"]
        if os.environ.get("REPO_PATH"):
            config.repo_path = os.environ["REPO_PATH"]

        return config

    def _create_adapter(self) -> AIAgentAdapter:
        """Cria adapter de IA delegando para PlatformFactory."""
        stderr_to_log = os.environ.get("MESSAGING_PROVIDER") == "tui"
        return PlatformFactory.create_adapter_for_provider(
            config=self.config,
            working_dir=str(self._paths.workspace),
            agents_dir=str(self._paths.agents_dir),
            global_skills_dir=str(self._paths.global_skills_dir),
            state_dir=str(self._paths.state_dir),
            stderr_to_log=stderr_to_log,
        )

    def _create_message_bus(self) -> MessageBus:
        """Cria instância de MessageBus via registry."""
        load_builtin_providers()
        provider_name = self.config.messaging_provider
        provider_cls = get_provider(provider_name)

        # Instancia o provider — cada um lê suas env vars internamente
        activation_mode = self.config.activation_mode if self._config else "mention"
        bus = provider_cls(
            persona_name=f"ai-squad ({self._team_name})",
            persona_avatar="🤖",
            activation_mode=activation_mode,
        )
        logger.info("MessageBus: %s", provider_name)
        return bus

    def _validate_tokens(self) -> None:
        """Valida tokens obrigatórios: comuns + específicos do provider."""
        missing = self._config.validate_required_tokens() if self._config else []
        if missing:
            logger.error("Tokens obrigatórios não configurados: %s", missing)
            sys.exit(1)

    def _setup_components(self) -> None:
        """Inicializa factory, providers e engine."""
        self._config = self._load_config()
        self._validate_tokens()

        # Configura adapter de IA baseado no provider configurado
        adapter = self._create_adapter()
        self._adapter = adapter

        # Configura barramento de mensageria via registry
        self._bus = self._create_message_bus()

        # Configura state manager
        state_mgr = StateManager(state_dir=str(self._paths.state_dir))

        # Monta dict de personas incluindo squad-lead
        personas: dict[str, AgentConfig | SquadLeadConfig] = (
            dict(self.config.agents) if self.config.agents else {}
        )
        if self.config.squad_lead:
            personas["squad-lead"] = self.config.squad_lead

        # Registra personas no bus para filtragem de mensagens próprias (OAuth)
        self._bus.register_personas(personas)

        # Monta o engine de orquestracao
        self._engine = OrchestrationEngine(
            adapter,
            self._bus,
            state_mgr,
            workspace=str(self._paths.workspace),
            personas=personas,
            agents_dir=str(self._paths.agents_dir),
            agent_timeout=self.config.agent_timeout,
        )

        self._state_manager = state_mgr

        # Inicializa mapeamento thread ↔ demand para threads/tópicos
        self._thread_map = ThreadDemandMap(state_dir=str(self._paths.state_dir))

        # Inicializa thread tracker (estado do bot por thread)
        tt_config = self.config.thread_tracking
        self._thread_tracker = ThreadTracker(
            state_dir=str(self._paths.state_dir),
            standby_timeout=tt_config.standby_timeout,
            inactive_thread_ttl=tt_config.inactive_thread_ttl,
            handoff_message=tt_config.handoff_message,
        )
        self._thread_tracker.load()
        # Propaga thread_map e callback de criação de tópico para o engine
        self._engine._thread_map = self._thread_map
        self._engine._create_topic_callback = self._create_demand_topic

        # Configura knowledge base se habilitada (preset helpdesk)
        if self.config.knowledge.enabled:
            kb_path = Path(self.config.knowledge.knowledge_dir)
            if kb_path.is_absolute():
                # Caminho absoluto: usa direto (ex: /dados/knowledge, ~/docs/kb)
                kb_dir = kb_path.expanduser()
            else:
                # Caminho relativo: resolve a partir do .ai-squad/ (local) ou /app/ (docker)
                kb_dir = self._paths.config_path.parent / kb_path
            self._engine.configure_knowledge(
                str(kb_dir),
                use_qmd=self.config.knowledge.use_qmd,
            )
            # Reindexa ao iniciar
            if self._engine.knowledge:
                self._engine.knowledge.reindex_all()

        logger.info("Componentes inicializados para time '%s'", self._team_name)

    async def _resume_pending_work(self) -> None:
        """Verifica trabalho pendente e dispara Squad Lead para retomar.

        Injeta contexto rico: journal (decisoes anteriores), conversation
        (historico de chat) e changes pendentes (openspec).
        """
        chat_id = self.bus.default_chat_id
        if not chat_id:
            return

        # Coleta contexto de retomada
        resume_parts = []
        has_pending = False

        # 1. Journal — decisoes anteriores e proxima acao esperada
        try:
            journal_summary = self.engine._journal.get_active_summaries()
            if journal_summary and journal_summary != "Nenhuma demanda ativa.":
                resume_parts.append(f"DECISOES ANTERIORES:\n{journal_summary}")
                has_pending = True
        except Exception as e:
            logger.debug("Erro ao ler journal: %s", e)

        # 2. Changes ativas no workspace via openspec
        try:
            import subprocess as sp

            result = sp.run(
                ["openspec", "list", "--json"],
                capture_output=True,
                text=True,
                cwd=str(self._paths.workspace),
                timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json

                changes = json.loads(result.stdout)
                active = [c for c in changes if c.get("status") != "archived"]
                if active:
                    names = ", ".join(c.get("name", "?") for c in active)
                    resume_parts.append(f"CHANGES PENDENTES: {names}")
                    has_pending = True
        except Exception as e:
            logger.debug("Erro ao verificar changes: %s", e)

        # 3. State manager — demandas ativas
        try:
            pending = self._state_manager.get_pending_demands()
            if pending:
                for d in pending:
                    resume_parts.append(
                        f"DEMANDA: {d['demand_id']} — estado: {d.get('state', '?')}"
                    )
                has_pending = True
        except Exception as e:
            logger.debug("Erro ao verificar state: %s", e)

        if not has_pending:
            logger.info("Nenhum trabalho pendente para retomar.")
            return

        # Monta prompt de retomada com todo o contexto
        context = "\n".join(resume_parts)
        resume_prompt = (
            f"O SISTEMA REINICIOU. Voce e o Squad Lead e precisa retomar o trabalho.\n\n"
            f"{context}\n\n"
            f"INSTRUCOES DE RETOMADA:\n"
            f"1. Analise as decisoes anteriores e o estado atual\n"
            f"2. Use get_pipeline_state() para verificar o estado do pipeline\n"
            f"3. Retome da fase onde parou — chame start_agent() para o agente correto\n"
            f"4. NAO pergunte ao usuario — avalie e aja imediatamente\n"
            f"5. Informe o usuario sobre o que esta fazendo"
        )

        logger.info("Retomando trabalho pendente apos restart")
        try:
            await self.engine.run_squad_lead(
                self._squad_lead_conversation_id,
                chat_id,
                resume_prompt,
            )
        except Exception as e:
            logger.error("Erro ao retomar trabalho: %s", e)

    @staticmethod
    def _slugify(text: str, max_words: int = 5) -> str:
        """Converte texto em slug kebab-case."""
        # Remove acentos
        normalized = unicodedata.normalize("NFKD", text)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        # Lowercase, só alfanumericos e espacos
        clean = re.sub(r"[^a-z0-9\s]", "", ascii_text.lower())
        # Pega primeiras N palavras
        words = clean.split()[:max_words]
        return "-".join(words) if words else "demanda"

    def _generate_demand_id(self, text: str) -> str:
        """Gera ID legível para a demanda a partir do texto."""
        slug = self._slugify(text)
        short_id = uuid.uuid4().hex[:4]
        return f"{slug}-{short_id}"

    def _build_agent_commands(self) -> dict[str, str]:
        """Gera mapeamento comando → agente a partir dos agents da config."""
        commands = {}
        if self._config and self.config.agents:
            for agent_id, agent_cfg in self.config.agents.items():
                cmd = agent_cfg.command or f"/{agent_id}"
                commands[cmd] = agent_id
        return commands

    async def _handle_new_demand(
        self,
        text: str,
        image_path: str | None = None,
        *,
        thread_id: str | None = None,
        user_id: str = "",
    ) -> None:
        """Handler chamado quando uma nova mensagem chega via mensageria.

        Processa imediatamente — Squad Lead responde rapido via chamada SDK curta.
        Agentes pesados (PO, Dev, QA) rodam em background via start_agent.

        Em modo com threads, thread_id roteia para a demanda correta:
        - thread_id mapeado → demand_id correspondente
        - thread_id=None ou Geral → Squad Lead sessão geral
        """
        chat_id = self.bus.default_chat_id
        if not chat_id:
            # Fallback para providers sem chat_id global
            chat_id = user_id or "default"
        # Usa user_id do callback ou fallback para chat_id (DM)
        user_id = user_id or chat_id

        # Consulta ThreadTracker para decidir se deve processar
        # Em activation_mode "all", pula o tracker — processa toda mensagem
        activation = self.config.activation_mode if self._config else "mention"
        if thread_id and self._thread_tracker and activation != "all":
            # is_mention: verifica se o texto original menciona o bot
            bot_id = self.bus.bot_identifier
            has_mention = bool(bot_id and f"@{bot_id}".lower() in text.lower())
            action = self._thread_tracker.on_message(
                thread_id, is_bot=False, is_mention=has_mention, user_name=user_id
            )
            if action == ThreadAction.IGNORE:
                return
            if action == ThreadAction.HANDOFF:
                if self._thread_tracker.handoff_message_enabled:
                    await self.bus.send_message(
                        chat_id,
                        "Entendido, alguém assumiu. Me mencione se precisar de mim novamente.",
                        thread_id=thread_id,
                    )
                return

        # Roteamento por thread_id (threads/tópicos)
        routed_demand_id = None
        if thread_id and self._thread_map:
            routed_demand_id = self._thread_map.get_demand(thread_id)

        # Verifica comandos especiais (antes do mapeamento automático)
        if text.strip().lower() == "/help":
            await self._send_help(chat_id, thread_id=thread_id)
            return

        if text.strip().lower() == "/status":
            await self._send_status(chat_id, thread_id=thread_id)
            return

        if text.strip().lower().startswith("/stop"):
            await self._stop_agents(chat_id, text.strip(), thread_id=thread_id)
            return

        if text.strip().lower() == "/skills":
            await self._send_skills(chat_id, thread_id=thread_id)
            return

        # Tópico existente sem mapeamento → cria demand_id e mapeia automaticamente
        if thread_id and self._thread_map and not routed_demand_id:
            routed_demand_id = self._generate_demand_id(text)
            self._thread_map.add(thread_id, routed_demand_id)
            logger.info(
                "Tópico %s mapeado automaticamente → %s",
                thread_id,
                routed_demand_id,
            )

        # Detecta direcionamento a agente especifico (comandos da config)
        agent_commands = self._build_agent_commands()
        target_agent = None
        demand_text = text
        for cmd, agent_id in agent_commands.items():
            if text.strip().lower().startswith(cmd):
                target_agent = agent_id
                demand_text = text.strip()[len(cmd) :].strip()
                if not demand_text:
                    await self.bus.send_message(
                        chat_id,
                        f"Use: {cmd} <sua mensagem>\nExemplo: {cmd} Criar API de autenticacao",
                        thread_id=thread_id,
                    )
                    return
                break

        # Processa imediatamente (sem fila bloqueante)
        try:
            if target_agent:
                # Comando /<agente> → conversa direta com agente (background)
                demand_id = routed_demand_id or self._generate_demand_id(demand_text)
                logger.info("Conversa direta com %s: %s", target_agent, demand_id)
                asyncio.create_task(
                    self._run_direct_agent(demand_id, chat_id, target_agent, demand_text)
                )
            elif routed_demand_id:
                # Mensagem em tópico mapeado → Squad Lead com demand_id específico
                logger.info(
                    "Squad Lead (tópico %s → %s): %s", thread_id, routed_demand_id, demand_text[:50]
                )
                await self.engine.run_squad_lead(
                    routed_demand_id,
                    chat_id,
                    demand_text,
                    image_path=image_path,
                    thread_id=thread_id,
                )
            else:
                # Tópico Geral ou DM → Squad Lead sessão geral
                demand_id = self._squad_lead_conversation_id
                logger.info("Squad Lead: %s", demand_text[:50])
                await self.engine.run_squad_lead(
                    demand_id,
                    chat_id,
                    demand_text,
                    image_path=image_path,
                    thread_id=thread_id,
                )
        except Exception as e:
            logger.error("Erro ao processar mensagem: %s", e, exc_info=True)
            try:
                await self.bus.notify(chat_id, f"Erro ao processar: {e}", thread_id=thread_id)
            except Exception:
                logger.error("Falha ao notificar erro via mensageria")
        finally:
            # Limpa imagem temporária
            if image_path:
                try:
                    Path(image_path).unlink(missing_ok=True)
                except Exception:
                    pass

    async def _create_demand_topic(self, demand_id: str, title: str) -> str | None:
        """Cria tópico para uma demanda e persiste mapeamento."""
        if not self.bus.supports_threads or not self._thread_map:
            return None
        chat_id = self.bus.default_chat_id
        if not chat_id:
            return None
        thread_id = await self.bus.create_thread(chat_id, title)
        if thread_id:
            self._thread_map.add(thread_id, demand_id)
        return thread_id

    async def _send_help(self, chat_id: str, *, thread_id: str | None = None) -> None:
        """Envia mensagem de ajuda com comandos disponíveis."""
        sl = self.config.squad_lead if self._config else None
        sl_name = sl.name if sl else "Squad Lead"

        lines = ["Comandos disponiveis:\n"]

        if self._config and self.config.agents:
            for agent_id, agent_cfg in self.config.agents.items():
                cmd = agent_cfg.command or f"/{agent_id}"
                lines.append(f"{cmd} <mensagem> - Falar com {agent_cfg.name}")

        lines.append("/status - Ver agentes ativos")
        lines.append("/stop - Parar todos os agentes")
        lines.append("/stop <agente> - Parar agente especifico")
        lines.append("/skills - Ver skills disponiveis")
        lines.append("/help - Esta mensagem")
        lines.append(
            f"\nOu envie uma mensagem direta para falar com o {sl_name} (ele coordena o time)."
        )

        await self.bus.send_message(chat_id, "\n".join(lines), thread_id=thread_id)

    async def _send_skills(self, chat_id: str, *, thread_id: str | None = None) -> None:
        """Lista skills disponiveis nos 3 niveis."""
        lines = ["Skills disponiveis:\n"]

        # 1. Globais
        global_dir = self._paths.global_skills_dir
        if global_dir.exists():
            skills = [
                d.name for d in global_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
            ]
            if skills:
                lines.append("Globais:")
                for s in sorted(skills):
                    lines.append(f"  - {s}")
            else:
                lines.append("Globais: nenhuma")
        else:
            lines.append("Globais: nenhuma")

        # 2. Por agente
        agents_dir = self._paths.agents_dir

        if agents_dir.exists():
            lines.append("\nPor agente:")
            for agent_dir in sorted(agents_dir.iterdir()):
                if not agent_dir.is_dir():
                    continue
                skills_dir = agent_dir / "skills"
                if not skills_dir.exists():
                    continue
                skills = [
                    d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
                ]
                if skills:
                    lines.append(f"  {agent_dir.name}: {', '.join(sorted(skills))}")

        # 3. Projeto
        ws_skills = self._paths.workspace / ".claude" / "skills"

        if ws_skills.exists():
            skills = [
                d.name for d in ws_skills.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
            ]
            if skills:
                lines.append("\nProjeto:")
                for s in sorted(skills):
                    lines.append(f"  - {s}")

        if len(lines) == 1:
            lines.append("Nenhuma skill configurada.")

        await self.bus.send_message(chat_id, "\n".join(lines), thread_id=thread_id)

    async def _stop_agents(self, chat_id: str, text: str, *, thread_id: str | None = None) -> None:
        """Para agentes em execucao. /stop para todos, /stop <nome> para especifico."""
        parts = text.strip().split(maxsplit=1)
        target = parts[1].strip() if len(parts) > 1 else None

        running = self.engine._running_agents
        if not running:
            await self.bus.send_message(chat_id, "Nenhum agente rodando no momento.")
            return

        stopped = []
        for name, ra in list(running.items()):
            if target and name != target:
                continue
            if ra.status != "running" or not ra.task:
                continue

            ra.task.cancel()
            ra.status = "cancelled"
            stopped.append(name)
            logger.info("[%s] Agente cancelado pelo usuario", name)

        if stopped:
            labels = ", ".join(self.engine._get_agent_label(n) for n in stopped)
            await self.bus.send_message(chat_id, f"Agentes parados: {labels}", thread_id=thread_id)
        elif target:
            await self.bus.send_message(
                chat_id,
                f"Agente '{target}' nao encontrado ou nao esta rodando.",
                thread_id=thread_id,
            )
        else:
            await self.bus.send_message(
                chat_id,
                "Nenhum agente em execucao para parar.",
                thread_id=thread_id,
            )

    async def _run_direct_agent(
        self,
        demand_id: str,
        user_id: str,
        agent_name: str,
        text: str,
    ) -> None:
        """Executa conversa direta com agente em background task."""
        try:
            await self.engine.direct_agent_conversation(
                demand_id,
                user_id,
                agent_name,
                text,
            )
        except Exception as e:
            logger.error("Erro na conversa com %s: %s", agent_name, e, exc_info=True)
            try:
                await self.bus.notify(user_id, f"Erro na conversa com {agent_name}: {e}")
            except Exception:
                pass

    async def _send_status(self, chat_id: str, *, thread_id: str | None = None) -> None:
        """Envia status dos agentes ativos. Em tópico, filtra pela demanda."""
        # Em tópico mapeado, mostra só agentes daquela demanda
        demand_id = None
        if thread_id and self._thread_map:
            demand_id = self._thread_map.get_demand(thread_id)

        if demand_id:
            # Filtra agentes desta demanda
            agents = self.engine._running_agents
            filtered = {k: v for k, v in agents.items() if v.demand_id == demand_id}
            if filtered:
                from src.orchestrator.prompt_builder import get_running_agents_status

                status = get_running_agents_status(filtered, self.engine._personas)
            else:
                status = f"Nenhum agente ativo para demanda {demand_id}."
        else:
            status = self.engine._get_running_agents_status()

        await self.bus.send_message(chat_id, status, thread_id=thread_id)

    def _write_healthcheck(self) -> None:
        """Escreve arquivo de heartbeat para health check do Docker."""
        Path("/tmp/ai-squad-healthy").touch()

    def _remove_healthcheck(self) -> None:
        """Remove arquivo de heartbeat."""
        health_file = Path("/tmp/ai-squad-healthy")
        if health_file.exists():
            health_file.unlink()

    async def _heartbeat_loop(self) -> None:
        """Verifica periodicamente demandas paradas e envia lembretes."""
        if not self._config or not self.config.heartbeat.enabled:
            return

        hb = self.config.heartbeat
        journal = JournalStore(state_dir=self.config.state_dir)
        chat_id = self.bus.default_chat_id

        logger.info(
            "Heartbeat ativo (intervalo: %ds, stall: %ds, reminder: %ds)",
            hb.interval,
            hb.stall_timeout,
            hb.reminder_timeout,
        )

        while not self._shutdown_event.is_set():
            await asyncio.sleep(hb.interval)
            try:
                # Verifica demandas paradas (não em approval)
                stalled = journal.get_stalled(stall_timeout=hb.stall_timeout)
                for demand in stalled:
                    retries = demand.get("auto_retries", 0)
                    if retries >= hb.max_auto_retries:
                        logger.warning(
                            "Demanda %s atingiu max retries (%d)",
                            demand["demand_id"],
                            retries,
                        )
                        continue

                    journal.increment_retries(demand["demand_id"])
                    demand_text = demand.get("demand_text", "?")
                    next_exp = demand.get("next_expected", {})
                    desc = next_exp.get("description", demand_text)

                    logger.info("Retomando demanda parada: %s", demand["demand_id"])
                    await self.engine.run_squad_lead(
                        demand["demand_id"],
                        chat_id,
                        f"RETOMADA AUTOMATICA: A demanda '{demand_text}' esta parada. "
                        f"Ultimo estado: {demand.get('current_phase', '?')}. "
                        f"Proximo esperado: {desc}. "
                        f"Avalie o estado e retome o trabalho.",
                    )

                # Verifica aprovações pendentes há muito tempo
                pending = journal.get_pending_approvals(
                    reminder_timeout=hb.reminder_timeout,
                )
                for demand in pending:
                    demand_text = demand.get("demand_text", "?")
                    if chat_id and self._bus:
                        await self._bus.send_message(
                            chat_id,
                            f"Lembrete: demanda '{demand_text}' aguarda sua aprovacao.",
                        )

            except Exception as e:
                logger.error("Erro no heartbeat: %s", e)

    async def _healthcheck_loop(self) -> None:
        """Atualiza heartbeat periodicamente."""
        while not self._shutdown_event.is_set():
            self._write_healthcheck()
            await asyncio.sleep(10)

    async def _standby_timeout_loop(self) -> None:
        """Verifica periodicamente threads em standby cujo timeout expirou."""
        if not self._thread_tracker:
            return

        check_interval = min(self._thread_tracker.standby_timeout // 3, 300)
        while not self._shutdown_event.is_set():
            await asyncio.sleep(check_interval)
            try:
                stale = self._thread_tracker.get_stale_standby_threads()
                chat_id = self.bus.default_chat_id
                for thread_id, info in stale:
                    if chat_id:
                        await self.bus.send_message(
                            chat_id,
                            "Sem atualizações há um tempo. Precisa de ajuda? Me mencione se sim.",
                            thread_id=thread_id,
                        )
                    self._thread_tracker.reactivate(thread_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Erro no standby timeout check: %s", e)

    async def run(self) -> None:
        """Inicia o daemon: conecta à mensageria e processa demandas."""
        logger.info("Iniciando daemon ai-squad (time: %s)", self._team_name)

        self._setup_components()

        # Registra handler de mensagens
        await self.bus.receive_message(self._handle_new_demand)

        # Registra handler de voz (transcrição → texto → demanda)
        async def _voice_handler(
            text: str, *, thread_id: str | None = None, user_id: str = ""
        ) -> None:
            await self._handle_new_demand(text, thread_id=thread_id, user_id=user_id)

        await self.bus.receive_voice(_voice_handler)

        # Registra handler de fotos
        async def _photo_handler(
            text: str, image_path: str, *, thread_id: str | None = None, user_id: str = ""
        ) -> None:
            await self._handle_new_demand(
                text, image_path=image_path, thread_id=thread_id, user_id=user_id
            )

        if hasattr(self.bus, "receive_photo"):
            await self.bus.receive_photo(_photo_handler)

        # Registra handler de documentos (helpdesk — ingestão de PDF/DOCX/etc)
        async def _document_handler(
            caption: str,
            file_path: str,
            *,
            thread_id: str | None = None,
            user_id: str = "",
            original_filename: str = "",
        ) -> None:
            text = f"Documento recebido: {original_filename}. {caption}"
            await self._handle_new_demand(text, thread_id=thread_id, user_id=user_id)

        if hasattr(self.bus, "receive_document"):
            await self.bus.receive_document(_document_handler)

        # Registra handler de reações (helpdesk — reforço positivo/negativo)
        async def _reaction_handler(
            chat_id: str, message_id: int, emoji: str, user_id: str
        ) -> None:
            tracker = self._engine.reaction_tracker if self._engine else None
            if tracker:
                tracker.on_reaction(message_id, emoji)

        if hasattr(self.bus, "on_reaction"):
            await self.bus.on_reaction(_reaction_handler)

        # Registra signal handlers para graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self._shutdown()))

        # Retoma trabalho pendente de execução anterior
        await self._resume_pending_work()

        # Notifica início via mensageria
        chat_id = self.bus.default_chat_id
        if chat_id:
            await self.bus.notify(
                chat_id,
                f"Time '{self._team_name}' online e escutando. "
                "Envie uma mensagem para criar uma demanda.",
            )

        logger.info("Daemon pronto. Escutando mensageria (%s)...", self.config.messaging_provider)

        # Inicia o provider de mensageria (polling, websocket, etc)
        await self.bus.start()

        # Healthcheck em background
        health_task = asyncio.create_task(self._healthcheck_loop())

        # Heartbeat para retomada de demandas paradas
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Thread tracker — check periódico de standby timeout
        standby_task = asyncio.create_task(self._standby_timeout_loop())

        try:
            # Se o bus implementa run_forever (ex: TUI), usa como loop principal
            run_forever_result = await self.bus.run_forever()
            if run_forever_result is None:
                # Bus padrão (Telegram, GChat) — aguarda sinal de shutdown
                await self._shutdown_event.wait()
        finally:
            health_task.cancel()
            heartbeat_task.cancel()
            standby_task.cancel()

            # Para o provider de mensageria
            await self.bus.stop()

            self._remove_healthcheck()
            logger.info("Daemon encerrado.")

    async def _shutdown(self) -> None:
        """Graceful shutdown: salva estado e notifica."""
        logger.info("Sinal de shutdown recebido.")

        # Notifica via mensageria
        try:
            chat_id = self._bus.default_chat_id if self._bus else ""
            if chat_id and self._bus:
                await self._bus.notify(
                    chat_id,
                    f"Time '{self._team_name}' encerrando...",
                )
        except Exception:
            pass

        # Shutdown do adapter (ex: Copilot SDK precisa parar o client)
        if self._adapter:
            try:
                await self._adapter.shutdown()
            except Exception as e:
                logger.warning("Erro no shutdown do adapter: %s", e)

        self._shutdown_event.set()


def main() -> None:
    """Entry point do daemon."""
    daemon = Daemon()
    asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
