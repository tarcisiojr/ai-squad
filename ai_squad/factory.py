"""Factory para instanciação de providers via configuração."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.messaging.interface import MessageBus

logger = logging.getLogger("ai-squad.factory")

# Prefixo de placeholder para tokens não preenchidos
_PLACEHOLDER_PREFIX = "PREENCHA_AQUI_"

# Token obrigatório por provider de IA (vazio = sem token obrigatório)
_PROVIDER_AI_TOKENS: dict[str, str] = {
    "agno": "GOOGLE_API_KEY",
    "copilot": "",  # autentica via 'copilot auth login', sem token no .env
}


@dataclass
class SubmoduleConfig:
    """Configuracao de um submodulo git."""

    path: str  # caminho relativo no workspace (ex: "packages/api")
    description: str = ""  # descricao opcional para o Squad Lead


@dataclass
class AgentConfig:
    """Configuracao de um agente."""

    name: str
    avatar: str
    command: str = ""
    agents_md: str = ""
    role: str = ""  # papel do agente: spec, dev, review, generic (vazio = inferir)
    timeout: int = 0  # 0 = usa agent_timeout padrao
    tools: list[str] = field(
        default_factory=list
    )  # toolkits extras: web_search, code_execution, shell
    web_search_provider: str = ""  # provider de web search: duckduckgo (default), tavily, serpapi
    submodules: list[SubmoduleConfig] = field(
        default_factory=list
    )  # submodulos que o agente trabalha


VALID_ACTIVATION_MODES = ("mention", "all", "command")


@dataclass
class ThreadTrackingConfig:
    """Configuração do rastreamento de estado por thread."""

    standby_timeout: int = 1800  # 30min — bot oferece ajuda se humano sumiu
    inactive_thread_ttl: int = 86400  # 24h — limpa threads inativas
    handoff_message: bool = True  # envia "Fulano assumiu" ao recuar


@dataclass
class HeartbeatConfig:
    """Configuração do heartbeat loop para retomada de demandas paradas."""

    enabled: bool = True
    interval: int = 300
    stall_timeout: int = 1800
    reminder_timeout: int = 3600
    max_auto_retries: int = 3


@dataclass
class SquadLeadConfig:
    """Configuracao do Squad Lead (agente coordenador obrigatorio)."""

    name: str = "Squad Lead"
    avatar: str = "👨‍💼"


@dataclass
class KnowledgeConfig:
    """Configuração da knowledge base (preset helpdesk)."""

    enabled: bool = False
    use_qmd: bool = False
    knowledge_dir: str = "knowledge/"  # relativo ao diretório do time


@dataclass
class PlatformConfig:
    """Configuracao centralizada da plataforma.

    Carregada de config.yaml com override por variaveis de ambiente.
    """

    ai_provider: str
    messaging_provider: str
    activation_mode: str = "mention"
    thread_tracking: ThreadTrackingConfig = field(default_factory=ThreadTrackingConfig)
    agent_timeout: int = 300
    state_dir: str = "state/"
    repo_path: str = ""
    ai_model: str | None = None
    light_model: str | None = None  # modelo leve para mensagens simples
    heavy_model: str | None = None  # modelo pesado para mensagens complexas
    squad_lead: SquadLeadConfig = field(default_factory=SquadLeadConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    knowledge: KnowledgeConfig = field(default_factory=KnowledgeConfig)
    agents: dict[str, AgentConfig] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PlatformConfig":
        """Carrega configuração a partir de arquivo YAML."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo de configuração não encontrado: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError("Configuração inválida: formato YAML incorreto")

        if "ai_provider" not in data:
            raise ValueError("Configuração inválida: 'ai_provider' é obrigatório")

        if "messaging_provider" not in data:
            raise ValueError("Configuração inválida: 'messaging_provider' é obrigatório")

        # Processar activation_mode
        activation_mode = data.get("activation_mode", "mention")
        if activation_mode not in VALID_ACTIVATION_MODES:
            raise ValueError(
                f"Configuração inválida: 'activation_mode' deve ser um de "
                f"{VALID_ACTIVATION_MODES}, mas recebeu '{activation_mode}'"
            )

        # Processar thread_tracking
        tt_data = data.get("thread_tracking", {})
        thread_tracking = ThreadTrackingConfig(
            standby_timeout=tt_data.get("standby_timeout", 1800),
            inactive_thread_ttl=tt_data.get("inactive_thread_ttl", 86400),
            handoff_message=tt_data.get("handoff_message", True),
        )

        # Processar heartbeat
        hb_data = data.get("heartbeat", {})
        heartbeat = HeartbeatConfig(
            enabled=hb_data.get("enabled", True),
            interval=hb_data.get("interval", 300),
            stall_timeout=hb_data.get("stall_timeout", 1800),
            reminder_timeout=hb_data.get("reminder_timeout", 3600),
            max_auto_retries=hb_data.get("max_auto_retries", 3),
        )

        # Processar knowledge base (helpdesk)
        kb_data = data.get("knowledge", {})
        knowledge = KnowledgeConfig(
            enabled=kb_data.get("enabled", False),
            use_qmd=kb_data.get("use_qmd", False),
            knowledge_dir=kb_data.get("knowledge_dir", "knowledge/"),
        )

        # Processar squad_lead
        sl_data = data.get("squad_lead", {})
        squad_lead = SquadLeadConfig(
            name=sl_data.get("name", "Squad Lead"),
            avatar=sl_data.get("avatar", "👨‍💼"),
        )

        # Processar agents (com fallback para personas)
        agents_data = data.get("agents", data.get("personas", {}))
        agents = {}
        for nome, config in agents_data.items():
            # Processa submodules (lista opcional)
            subs_data = config.get("submodules", [])
            submodules = []
            for sub in subs_data:
                if isinstance(sub, str):
                    submodules.append(SubmoduleConfig(path=sub))
                elif isinstance(sub, dict):
                    submodules.append(
                        SubmoduleConfig(
                            path=sub.get("path", ""),
                            description=sub.get("description", ""),
                        )
                    )

            agents[nome] = AgentConfig(
                name=config.get("name", nome),
                avatar=config.get("avatar", ""),
                command=config.get("command", f"/{nome}"),
                role=config.get("role", ""),
                timeout=config.get("timeout", 0),
                tools=config.get("tools", []),
                web_search_provider=config.get("web_search_provider", ""),
                submodules=submodules,
            )

        instance = cls(
            ai_provider=data["ai_provider"],
            messaging_provider=data["messaging_provider"],
            activation_mode=activation_mode,
            thread_tracking=thread_tracking,
            agent_timeout=data.get("agent_timeout", 300),
            state_dir=data.get("state_dir", "state/"),
            repo_path=data.get("repo_path", ""),
            ai_model=data.get("ai_model"),
            light_model=data.get("light_model"),
            heavy_model=data.get("heavy_model"),
            squad_lead=squad_lead,
            heartbeat=heartbeat,
            knowledge=knowledge,
            agents=agents,
        )

        # Variáveis de ambiente sobrescrevem valores do YAML
        instance._apply_env_overrides()

        # Resolve repo_path para caminho absoluto
        if instance.repo_path:
            instance.repo_path = str(Path(instance.repo_path).expanduser().resolve())

        return instance

    def _apply_env_overrides(self) -> None:
        """Aplica variáveis de ambiente sobre a configuração carregada."""
        env_map = {
            "AI_PROVIDER": "ai_provider",
            "MESSAGING_PROVIDER": "messaging_provider",
            "AGENT_TIMEOUT": "agent_timeout",
            "STATE_DIR": "state_dir",
            "REPO_PATH": "repo_path",
            "AI_MODEL": "ai_model",
        }

        for env_var, attr in env_map.items():
            value = os.environ.get(env_var)
            if value:
                if attr == "agent_timeout":
                    setattr(self, attr, int(value))
                else:
                    setattr(self, attr, value)

    def validate_required_tokens(self) -> list[str]:
        """Valida que tokens obrigatórios estão configurados.

        Verifica tokens comuns + tokens específicos do provider de mensageria.
        Retorna lista de tokens ausentes ou com placeholder.
        """
        missing = []
        token_var = _PROVIDER_AI_TOKENS.get(self.ai_provider, "CLAUDE_CODE_OAUTH_TOKEN")
        if token_var:  # vazio = provider sem token obrigatório
            token_val = os.environ.get(token_var, "")
            if not token_val or token_val.startswith(_PLACEHOLDER_PREFIX):
                missing.append(token_var)

        # Tokens específicos do provider de mensageria
        try:
            from ai_squad.messaging.registry import get as get_provider
            from ai_squad.messaging.registry import load_builtin_providers

            load_builtin_providers()
            provider_cls = get_provider(self.messaging_provider)
            for var_name in provider_cls.required_env_vars():
                value = os.environ.get(var_name, "")
                if not value or value.startswith(_PLACEHOLDER_PREFIX):
                    missing.append(var_name)
        except (ValueError, ImportError):
            pass

        return missing


class PlatformFactory:
    """Factory para criação de instâncias de providers.

    Mantém mapeamento de nomes de providers para suas implementações
    e instancia via configuração centralizada.
    """

    def __init__(self) -> None:
        self._message_bus_providers: dict[str, type[MessageBus]] = {}
        self._ai_adapter_providers: dict[str, type[AIAgentAdapter]] = {}

    def register_message_bus(self, name: str, cls: type[MessageBus]) -> None:
        """Registra implementação de MessageBus por nome."""
        self._message_bus_providers[name] = cls

    def register_ai_adapter(self, name: str, cls: type[AIAgentAdapter]) -> None:
        """Registra implementação de AIAgentAdapter por nome."""
        self._ai_adapter_providers[name] = cls

    def create_message_bus(self, config: PlatformConfig, **kwargs: Any) -> MessageBus:
        """Cria instância de MessageBus baseada na configuração."""
        provider = config.messaging_provider
        if provider not in self._message_bus_providers:
            raise ValueError(
                f"Provider de mensageria não registrado: '{provider}'. "
                f"Disponíveis: {list(self._message_bus_providers.keys())}"
            )
        return self._message_bus_providers[provider](**kwargs)

    def create_ai_adapter(self, config: PlatformConfig, **kwargs: Any) -> AIAgentAdapter:
        """Cria instância de AIAgentAdapter baseada na configuração."""
        provider = config.ai_provider
        if provider not in self._ai_adapter_providers:
            raise ValueError(
                f"Provider de IA não registrado: '{provider}'. "
                f"Disponíveis: {list(self._ai_adapter_providers.keys())}"
            )
        if config.ai_model and "model" not in kwargs:
            kwargs["model"] = config.ai_model
        return self._ai_adapter_providers[provider](**kwargs)

    @staticmethod
    def create_adapter_for_provider(
        config: PlatformConfig,
        *,
        working_dir: str,
        agents_dir: str,
        global_skills_dir: str,
        state_dir: str = "",
        stderr_to_log: bool = False,
    ) -> AIAgentAdapter:
        """Cria adapter de IA baseado no provider configurado.

        Realiza import condicional das classes concretas internamente,
        mantendo o acoplamento com implementações dentro da factory.
        """
        kwargs: dict[str, Any] = {
            "timeout": config.agent_timeout,
            "working_dir": working_dir,
            "allowed_tools": ["WebSearchTool"],
            "agents_dir": agents_dir,
            "global_skills_dir": global_skills_dir,
        }

        if config.ai_model:
            kwargs["model"] = config.ai_model

        provider = config.ai_provider

        if provider == "copilot":
            return PlatformFactory._create_copilot_adapter(kwargs)
        elif provider == "agno":
            return PlatformFactory._create_agno_adapter(kwargs, state_dir=state_dir)
        else:
            return PlatformFactory._create_claude_adapter(
                kwargs,
                config=config,
                agents_dir=agents_dir,
                stderr_to_log=stderr_to_log,
            )

    @staticmethod
    def _create_claude_adapter(
        kwargs: dict[str, Any],
        *,
        config: PlatformConfig,
        agents_dir: str,
        stderr_to_log: bool = False,
    ) -> AIAgentAdapter:
        """Cria adapter Claude Agent SDK."""
        from ai_squad.adapters.claude_agent_sdk import ClaudeAgentSDKAdapter

        logger.info("Usando adapter: Claude Agent SDK (model: %s)", config.ai_model)
        adapter = ClaudeAgentSDKAdapter(**kwargs)

        # No modo TUI, redireciona stderr do subprocess para log
        if stderr_to_log:
            adapter._stderr_to_log = True

        # Configura subagentes nativos do SDK a partir dos AGENTS.md
        agent_defs = PlatformFactory._build_agent_definitions(config, agents_dir)
        if agent_defs:
            adapter.set_agent_definitions(agent_defs)
            logger.info("Subagentes configurados: %s", list(agent_defs.keys()))

        return adapter

    @staticmethod
    def _create_copilot_adapter(kwargs: dict[str, Any]) -> AIAgentAdapter:
        """Cria adapter Copilot SDK (import condicional)."""
        try:
            from ai_squad.adapters.copilot_adapter import CopilotAdapter
        except ImportError as e:
            logger.error(
                "Provider 'copilot' selecionado mas dependencias nao instaladas. "
                "Instale com: pip install -e '.[copilot]': %s",
                e,
            )
            raise RuntimeError(
                "Dependencias do Copilot SDK nao instaladas. Use: pip install -e '.[copilot]'"
            ) from e

        logger.info("Usando adapter: Copilot SDK")
        return CopilotAdapter(**kwargs)

    @staticmethod
    def _create_agno_adapter(kwargs: dict[str, Any], *, state_dir: str = "") -> AIAgentAdapter:
        """Cria adapter Agno (import condicional)."""
        try:
            from ai_squad.adapters.agno_adapter import AgnoAdapter
        except ImportError as e:
            logger.error(
                "Provider 'agno' selecionado mas dependencias nao instaladas. "
                "Instale com: pip install -e '.[agno]': %s",
                e,
            )
            raise RuntimeError(
                "Dependencias do Agno nao instaladas. Use: pip install -e '.[agno]'"
            ) from e

        kwargs["state_dir"] = state_dir
        logger.info("Usando adapter: Agno")
        return AgnoAdapter(**kwargs)

    @staticmethod
    def _build_agent_definitions(config: PlatformConfig, agents_dir: str) -> dict:
        """Constroi AgentDefinition para cada agente a partir dos AGENTS.md."""
        from claude_agent_sdk import AgentDefinition

        agents_path = Path(agents_dir)
        defs = {}

        if not config.agents:
            return defs

        for agent_id, agent_cfg in config.agents.items():
            agents_md_path = agents_path / agent_id / "AGENTS.md"
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
