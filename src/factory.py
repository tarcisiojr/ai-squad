"""Factory para instanciação de providers via configuração."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.barramento.interface import MessageBus
from src.adapters.interface import AIAgentAdapter

# Prefixo de placeholder para tokens não preenchidos
_PLACEHOLDER_PREFIX = "PREENCHA_AQUI_"


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
    done_marker: str = ""
    agents_md: str = ""
    role: str = ""  # papel do agente: spec, dev, review, generic (vazio = inferir)
    timeout: int = 0  # 0 = usa agent_timeout padrao
    submodules: list[SubmoduleConfig] = field(default_factory=list)  # submodulos que o agente trabalha


# Alias para retrocompatibilidade
PersonaConfig = AgentConfig


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
class PlatformConfig:
    """Configuracao centralizada da plataforma.

    Carregada de config.yaml com override por variaveis de ambiente.
    """

    ai_provider: str
    messaging_provider: str
    agent_timeout: int = 300
    dev_timeout: int = 600
    state_dir: str = "state/"
    repo_path: str = ""
    ai_model: str | None = None
    light_model: str | None = None  # modelo leve para mensagens simples
    heavy_model: str | None = None  # modelo pesado para mensagens complexas
    squad_lead: SquadLeadConfig = field(default_factory=SquadLeadConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    agents: dict[str, AgentConfig] = field(default_factory=dict)

    @property
    def personas(self) -> dict[str, AgentConfig]:
        """Alias para retrocompatibilidade."""
        return self.agents

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
            raise ValueError(
                "Configuração inválida: 'messaging_provider' é obrigatório"
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
                    submodules.append(SubmoduleConfig(
                        path=sub.get("path", ""),
                        description=sub.get("description", ""),
                    ))

            agents[nome] = AgentConfig(
                name=config.get("name", nome),
                avatar=config.get("avatar", ""),
                command=config.get("command", f"/{nome}"),
                done_marker=config.get("done_marker", ""),
                role=config.get("role", ""),
                timeout=config.get("timeout", 0),
                submodules=submodules,
            )

        instance = cls(
            ai_provider=data["ai_provider"],
            messaging_provider=data["messaging_provider"],
            agent_timeout=data.get("agent_timeout", 300),
            dev_timeout=data.get("dev_timeout", 600),
            state_dir=data.get("state_dir", "state/"),
            repo_path=data.get("repo_path", ""),
            ai_model=data.get("ai_model"),
            light_model=data.get("light_model"),
            heavy_model=data.get("heavy_model"),
            squad_lead=squad_lead,
            heartbeat=heartbeat,
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

        Retorna lista de tokens ausentes ou com placeholder.
        """
        required = {
            "CLAUDE_CODE_OAUTH_TOKEN": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", ""),
            "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
            "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN", ""),
            "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", ""),
        }

        return [
            k for k, v in required.items()
            if not v or v.startswith(_PLACEHOLDER_PREFIX)
        ]


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

    def create_ai_adapter(
        self, config: PlatformConfig, **kwargs: Any
    ) -> AIAgentAdapter:
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
