"""Daemon do ai-squad — loop infinito escutando Telegram."""

import asyncio
import logging
import os
import re
import signal
import sys
import unicodedata
import uuid
from pathlib import Path

from dotenv import load_dotenv

from src.adapters.claude_agent_sdk import ClaudeAgentSDKAdapter
from src.factory import PlatformConfig
from src.messaging.telegram import TelegramMessageBus
from src.orchestrator.engine import OrchestrationEngine
from src.orchestrator.journal import JournalStore
from src.orchestrator.state import StateManager

# Configuração de logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai-squad.daemon")


class Daemon:
    """Processo daemon que escuta Telegram e orquestra demandas.

    Roda em loop infinito (Docker ou local foreground).
    Processa uma demanda por vez, enfileirando as demais.
    """

    def __init__(self, path_resolver: "PathResolver | None" = None) -> None:
        from src.path_resolver import PathResolver

        self._shutdown_event = asyncio.Event()
        self._engine: OrchestrationEngine | None = None
        self._bus: TelegramMessageBus | None = None
        self._config: PlatformConfig | None = None
        self._paths = path_resolver or PathResolver("docker")
        # Conversa continua com o Squad Lead (sem criar demanda)
        self._squad_lead_conversation_id = "squad-lead-session"
        self._team_name = os.environ.get("TEAM_NAME", "default")

    @property
    def engine(self) -> OrchestrationEngine:
        """Acesso seguro ao engine — falha se não inicializado."""
        assert self._engine is not None, (
            "Engine não inicializado — chame _setup_components primeiro"
        )
        return self._engine

    @property
    def bus(self) -> TelegramMessageBus:
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

    def _create_adapter(self):
        """Cria adapter de IA via Claude Agent SDK."""
        kwargs = {
            "timeout": self.config.agent_timeout,
            "working_dir": str(self._paths.workspace),
            "allowed_tools": ["WebSearchTool"],
            "agents_dir": str(self._paths.agents_dir),
            "global_skills_dir": str(self._paths.global_skills_dir),
        }

        if self.config.ai_model:
            kwargs["model"] = self.config.ai_model

        logger.info("Usando adapter: Claude Agent SDK (model: %s)", self.config.ai_model)
        adapter = ClaudeAgentSDKAdapter(**kwargs)

        # Configura subagentes nativos do SDK a partir dos AGENTS.md
        agent_defs = self._build_agent_definitions()
        if agent_defs:
            adapter.set_agent_definitions(agent_defs)
            logger.info("Subagentes configurados: %s", list(agent_defs.keys()))

        return adapter

    def _build_agent_definitions(self) -> dict:
        """Constroi AgentDefinition para cada agente a partir dos AGENTS.md."""
        from claude_agent_sdk import AgentDefinition

        agents_dir = self._paths.agents_dir
        defs = {}

        if not self._config or not self.config.agents:
            return defs

        for agent_id, agent_cfg in self.config.agents.items():
            agents_md_path = agents_dir / agent_id / "AGENTS.md"
            prompt = ""
            if agents_md_path.exists():
                try:
                    prompt = agents_md_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    prompt = f"Voce e o agente {agent_cfg.name}."

            if not prompt:
                prompt = f"Voce e o agente {agent_cfg.name}."

            defs[agent_id] = AgentDefinition(
                description=f"{agent_cfg.avatar} {agent_cfg.name}",
                prompt=prompt,
            )

        return defs

    def _validate_tokens(self) -> None:
        """Valida tokens obrigatórios. Delega para PlatformConfig quando disponível."""
        if self._config:
            missing = self._config.validate_required_tokens()
        else:
            # Fallback direto (antes de _load_config ou em testes)
            from src.factory import _PLACEHOLDER_PREFIX

            required = {
                "CLAUDE_CODE_OAUTH_TOKEN": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", ""),
                "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
                "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN", ""),
                "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", ""),
            }
            missing = [k for k, v in required.items() if not v or v.startswith(_PLACEHOLDER_PREFIX)]
        if missing:
            logger.error("Tokens obrigatórios não configurados: %s", missing)
            sys.exit(1)

    def _setup_components(self) -> None:
        """Inicializa factory, providers e engine."""
        self._config = self._load_config()
        self._validate_tokens()

        # Configura adapter de IA baseado no provider configurado
        adapter = self._create_adapter()

        # Configura barramento Telegram
        telegram_token = os.environ["TELEGRAM_TOKEN"]
        whisper_key = os.environ.get("OPENAI_API_KEY")

        self._bus = TelegramMessageBus(
            token=telegram_token,
            persona_name=f"ai-squad ({self._team_name})",
            persona_avatar="🤖",
            whisper_api_key=whisper_key,
        )

        # Configura state manager
        state_mgr = StateManager(state_dir=str(self._paths.state_dir))

        # Monta dict de personas incluindo squad-lead
        personas = dict(self.config.agents) if self.config.agents else {}
        if self.config.squad_lead:
            personas["squad-lead"] = self.config.squad_lead

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
        logger.info("Componentes inicializados para time '%s'", self._team_name)

    async def _resume_pending_work(self) -> None:
        """Verifica trabalho pendente e dispara Squad Lead para retomar.

        Injeta contexto rico: journal (decisoes anteriores), conversation
        (historico de chat) e changes pendentes (openspec).
        """
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
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

    async def _handle_new_demand(self, text: str) -> None:
        """Handler chamado quando uma nova mensagem chega via Telegram.

        Processa imediatamente — Squad Lead responde rapido via chamada SDK curta.
        Agentes pesados (PO, Dev, QA) rodam em background via start_agent.
        """
        chat_id = os.environ["TELEGRAM_CHAT_ID"]

        # Verifica comandos especiais
        if text.strip().lower() == "/help":
            await self._send_help(chat_id)
            return

        if text.strip().lower() == "/status":
            await self._send_status(chat_id)
            return

        if text.strip().lower().startswith("/stop"):
            await self._stop_agents(chat_id, text.strip())
            return

        if text.strip().lower() == "/skills":
            await self._send_skills(chat_id)
            return

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
                    )
                    return
                break

        # Processa imediatamente (sem fila bloqueante)
        try:
            if target_agent:
                # Comando /<agente> → conversa direta com agente (background)
                demand_id = self._generate_demand_id(demand_text)
                logger.info("Conversa direta com %s: %s", target_agent, demand_id)
                asyncio.create_task(
                    self._run_direct_agent(demand_id, chat_id, target_agent, demand_text)
                )
            else:
                # Mensagem sem comando → Squad Lead (responde rapido)
                demand_id = self._squad_lead_conversation_id
                logger.info("Squad Lead: %s", demand_text[:50])
                await self.engine.run_squad_lead(
                    demand_id,
                    chat_id,
                    demand_text,
                )
        except Exception as e:
            logger.error("Erro ao processar mensagem: %s", e, exc_info=True)
            try:
                await self.bus.notify(chat_id, f"Erro ao processar: {e}")
            except Exception:
                logger.error("Falha ao notificar erro via Telegram")

    async def _send_help(self, chat_id: str) -> None:
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

        await self.bus.send_message(chat_id, "\n".join(lines))

    async def _send_skills(self, chat_id: str) -> None:
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

        await self.bus.send_message(chat_id, "\n".join(lines))

    async def _stop_agents(self, chat_id: str, text: str) -> None:
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
            await self.bus.send_message(chat_id, f"Agentes parados: {labels}")
        elif target:
            await self.bus.send_message(
                chat_id, f"Agente '{target}' nao encontrado ou nao esta rodando."
            )
        else:
            await self.bus.send_message(chat_id, "Nenhum agente em execucao para parar.")

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

    async def _send_status(self, chat_id: str) -> None:
        """Envia status dos agentes ativos."""
        status = self.engine._get_running_agents_status()
        await self.bus.send_message(chat_id, status)

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
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

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

    async def run(self) -> None:
        """Inicia o daemon: conecta ao Telegram e processa demandas."""
        logger.info("Iniciando daemon ai-squad (time: %s)", self._team_name)

        self._setup_components()

        # Registra handler de mensagens
        await self.bus.receive_message(self._handle_new_demand)

        # Registra handler de voz (transcrição → texto → demanda)
        async def _voice_handler(text: str) -> None:
            await self._handle_new_demand(text)

        await self.bus.receive_voice(_voice_handler)

        # Registra signal handlers para graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self._shutdown()))

        # Retoma trabalho pendente de execução anterior
        await self._resume_pending_work()

        # Notifica início via Telegram
        chat_id = os.environ["TELEGRAM_CHAT_ID"]
        await self.bus.notify(
            chat_id,
            f"Time '{self._team_name}' online e escutando. "
            "Envie uma mensagem para criar uma demanda.",
        )

        logger.info("Daemon pronto. Escutando Telegram...")

        # Inicia Telegram polling + healthcheck
        await self.bus._ensure_app()

        # Healthcheck em background
        health_task = asyncio.create_task(self._healthcheck_loop())

        # Heartbeat para retomada de demandas paradas
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        app = self.bus._app
        assert app is not None, "Telegram app não inicializado após _ensure_app"
        assert app.updater is not None, "Telegram updater não disponível"

        try:
            # Inicia polling do Telegram (bloqueante)
            await app.initialize()
            await app.start()
            await app.updater.start_polling()

            # Aguarda sinal de shutdown
            await self._shutdown_event.wait()
        finally:
            health_task.cancel()
            heartbeat_task.cancel()

            # Para polling do Telegram
            if app.updater.running:
                await app.updater.stop()
            if app.running:
                await app.stop()
            await app.shutdown()

            self._remove_healthcheck()
            logger.info("Daemon encerrado.")

    async def _shutdown(self) -> None:
        """Graceful shutdown: salva estado e notifica."""
        logger.info("Sinal de shutdown recebido.")

        # Notifica via Telegram
        try:
            chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
            if chat_id and self._bus:
                await self._bus.notify(
                    chat_id,
                    f"Time '{self._team_name}' encerrando...",
                )
        except Exception:
            pass

        self._shutdown_event.set()


def main() -> None:
    """Entry point do daemon."""
    daemon = Daemon()
    asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
