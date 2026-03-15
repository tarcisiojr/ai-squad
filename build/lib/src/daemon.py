"""Daemon do ai-dev-team — loop infinito escutando Telegram."""

import asyncio
import logging
import os
import signal
import sys
import uuid
from collections import deque
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.adapters.claude_code import ClaudeCodeAdapter
from src.barramento.telegram import TelegramMessageBus
from src.factory import PlatformConfig, PlatformFactory
from src.orchestrator.engine import OrchestrationEngine
from src.orchestrator.state import StateManager

# Configuração de logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai-dev-team.daemon")


class Daemon:
    """Processo daemon que escuta Telegram e orquestra demandas.

    Roda em loop infinito dentro do container Docker.
    Processa uma demanda por vez, enfileirando as demais.
    """

    def __init__(self) -> None:
        self._shutdown_event = asyncio.Event()
        self._demand_queue: deque[dict] = deque()
        self._processing = False
        self._engine: OrchestrationEngine | None = None
        self._bus: TelegramMessageBus | None = None
        self._config: PlatformConfig | None = None
        self._team_name = os.environ.get("TEAM_NAME", "default")

    def _load_config(self) -> PlatformConfig:
        """Carrega configuração de config.yaml + variáveis de ambiente."""
        # Carrega .env se existir
        env_path = Path(".env")
        if env_path.exists():
            load_dotenv(env_path)

        # Carrega config.yaml base
        config_path = Path("config.yaml")
        if config_path.exists():
            config = PlatformConfig.from_yaml(config_path)
        else:
            config = PlatformConfig(
                ai_provider=os.environ.get("AI_PROVIDER", "claude-code"),
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

    def _validate_tokens(self) -> None:
        """Valida que tokens obrigatórios estão configurados."""
        required = {
            "CLAUDE_CODE_OAUTH_TOKEN": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", ""),
            "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
            "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN", ""),
            "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", ""),
        }

        missing = [k for k, v in required.items() if not v or v.startswith("PREENCHA_AQUI_")]
        if missing:
            logger.error("Tokens obrigatórios não configurados: %s", missing)
            sys.exit(1)

    def _setup_components(self) -> None:
        """Inicializa factory, providers e engine."""
        self._config = self._load_config()
        self._validate_tokens()

        # Configura adapter de IA
        adapter = ClaudeCodeAdapter(
            timeout=self._config.agent_timeout,
            working_dir="/workspace",
        )

        # Configura barramento Telegram
        telegram_token = os.environ["TELEGRAM_TOKEN"]
        whisper_key = os.environ.get("OPENAI_API_KEY")

        self._bus = TelegramMessageBus(
            token=telegram_token,
            persona_name=f"ai-dev-team ({self._team_name})",
            persona_avatar="🤖",
            whisper_api_key=whisper_key,
        )

        # Configura state manager
        state_mgr = StateManager(state_dir=self._config.state_dir)

        # Monta o engine de orquestração
        self._engine = OrchestrationEngine(adapter, self._bus, state_mgr)

        logger.info("Componentes inicializados para time '%s'", self._team_name)

    async def _handle_new_demand(self, text: str) -> None:
        """Handler chamado quando uma nova mensagem chega via Telegram."""
        chat_id = os.environ["TELEGRAM_CHAT_ID"]
        demand_id = f"demand-{uuid.uuid4().hex[:8]}"

        demand = {
            "demand_id": demand_id,
            "user_id": chat_id,
            "text": text,
        }

        self._demand_queue.append(demand)
        queue_size = len(self._demand_queue)

        logger.info(
            "Nova demanda recebida: %s (fila: %d)",
            demand_id,
            queue_size,
        )

        if queue_size > 1:
            await self._bus.notify(
                chat_id,
                f"Demanda '{demand_id}' enfileirada. "
                f"Posição na fila: {queue_size}",
            )

    async def _process_queue(self) -> None:
        """Processa demandas da fila uma por vez."""
        while not self._shutdown_event.is_set():
            if not self._demand_queue:
                await asyncio.sleep(1)
                continue

            demand = self._demand_queue.popleft()
            self._processing = True

            logger.info(
                "Processando demanda: %s - %s",
                demand["demand_id"],
                demand["text"][:50],
            )

            try:
                await self._engine.run_demand_cycle(
                    demand["demand_id"],
                    demand["user_id"],
                    demand["text"],
                )
                logger.info("Demanda concluída: %s", demand["demand_id"])
            except Exception as e:
                logger.error(
                    "Erro na demanda %s: %s",
                    demand["demand_id"],
                    str(e),
                    exc_info=True,
                )
                try:
                    await self._bus.notify(
                        demand["user_id"],
                        f"Erro ao processar demanda {demand['demand_id']}: {e}",
                    )
                except Exception:
                    logger.error("Falha ao notificar erro via Telegram")
            finally:
                self._processing = False

    def _write_healthcheck(self) -> None:
        """Escreve arquivo de heartbeat para health check do Docker."""
        Path("/tmp/ai-dev-team-healthy").touch()

    def _remove_healthcheck(self) -> None:
        """Remove arquivo de heartbeat."""
        health_file = Path("/tmp/ai-dev-team-healthy")
        if health_file.exists():
            health_file.unlink()

    async def _healthcheck_loop(self) -> None:
        """Atualiza heartbeat periodicamente."""
        while not self._shutdown_event.is_set():
            self._write_healthcheck()
            await asyncio.sleep(10)

    async def run(self) -> None:
        """Inicia o daemon: conecta ao Telegram e processa demandas."""
        logger.info("Iniciando daemon ai-dev-team (time: %s)", self._team_name)

        self._setup_components()

        # Registra handler de mensagens
        await self._bus.receive_message(self._handle_new_demand)

        # Registra handler de voz (transcrição → texto → demanda)
        async def _voice_handler(text: str) -> None:
            await self._handle_new_demand(text)

        await self._bus.receive_voice(_voice_handler)

        # Registra signal handlers para graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self._shutdown()))

        # Notifica início via Telegram
        chat_id = os.environ["TELEGRAM_CHAT_ID"]
        await self._bus.notify(
            chat_id,
            f"Time '{self._team_name}' online e escutando. "
            "Envie uma mensagem para criar uma demanda.",
        )

        logger.info("Daemon pronto. Escutando Telegram...")

        # Inicia Telegram polling + processamento de fila + healthcheck
        await self._bus._ensure_app()

        # Roda processamento de fila e healthcheck em paralelo com polling
        queue_task = asyncio.create_task(self._process_queue())
        health_task = asyncio.create_task(self._healthcheck_loop())

        try:
            # Inicia polling do Telegram (bloqueante)
            await self._bus._app.initialize()
            await self._bus._app.start()
            await self._bus._app.updater.start_polling()

            # Aguarda sinal de shutdown
            await self._shutdown_event.wait()
        finally:
            queue_task.cancel()
            health_task.cancel()

            # Para polling do Telegram
            if self._bus._app.updater.running:
                await self._bus._app.updater.stop()
            if self._bus._app.running:
                await self._bus._app.stop()
            await self._bus._app.shutdown()

            self._remove_healthcheck()
            logger.info("Daemon encerrado.")

    async def _shutdown(self) -> None:
        """Graceful shutdown: salva estado e notifica."""
        logger.info("Sinal de shutdown recebido.")

        if self._processing:
            logger.info("Aguardando conclusão da etapa atual (max 30s)...")
            for _ in range(30):
                if not self._processing:
                    break
                await asyncio.sleep(1)

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
