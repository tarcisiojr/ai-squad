"""Factory para instanciação de providers via configuração."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.barramento.interface import MessageBus
from src.adapters.interface import AIAgentAdapter


@dataclass
class PersonaConfig:
    """Configuração de uma persona."""

    name: str
    avatar: str
    token: str | None = None


@dataclass
class PlatformConfig:
    """Configuração centralizada da plataforma.

    Carregada a partir do platform.yaml.
    """

    ai_provider: str
    messaging_provider: str
    agent_timeout: int = 300
    state_dir: str = "state/"
    personas: dict[str, PersonaConfig] = field(default_factory=dict)

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

        # Processar personas
        personas = {}
        for nome, config in data.get("personas", {}).items():
            personas[nome] = PersonaConfig(
                name=config.get("name", nome),
                avatar=config.get("avatar", ""),
                token=config.get("token"),
            )

        return cls(
            ai_provider=data["ai_provider"],
            messaging_provider=data["messaging_provider"],
            agent_timeout=data.get("agent_timeout", 300),
            state_dir=data.get("state_dir", "state/"),
            personas=personas,
        )


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
        return self._ai_adapter_providers[provider](**kwargs)
