"""Interface base e configuração de providers de geração."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    """Configuração de um provider de geração."""

    # Nome do ai_provider no config.yaml do time
    ai_provider: str
    # Variável de ambiente para o token no .env
    env_var: str
    # Modelo default usado na geração
    default_model: str


# Mapeamento provider → configuração do time
PROVIDER_CONFIGS: dict[str, ProviderConfig] = {
    "anthropic": ProviderConfig(
        ai_provider="claude-agent-sdk",
        env_var="CLAUDE_CODE_OAUTH_TOKEN",
        default_model="claude-haiku-4-5-20251001",
    ),
    "openai": ProviderConfig(
        ai_provider="openai",
        env_var="OPENAI_API_KEY",
        default_model="gpt-4o-mini",
    ),
    "agno": ProviderConfig(
        ai_provider="agno",
        env_var="GOOGLE_API_KEY",
        default_model="gemini-2.0-flash",
    ),
    "copilot": ProviderConfig(
        ai_provider="copilot",
        env_var="",
        default_model="",
    ),
}


def get_provider_config(provider_name: str) -> ProviderConfig:
    """Retorna configuração de um provider pelo nome."""
    if provider_name not in PROVIDER_CONFIGS:
        raise ValueError(f"Provider desconhecido: {provider_name}")
    return PROVIDER_CONFIGS[provider_name]


def get_provider(provider_name: str, token: str) -> "GeneratorProvider":
    """Instancia o GeneratorProvider correto pelo nome."""
    if provider_name == "anthropic":
        from src.cli.generators.anthropic import AnthropicGenerator

        return AnthropicGenerator(token)
    elif provider_name == "openai":
        from src.cli.generators.openai import OpenAIGenerator

        return OpenAIGenerator(token)
    elif provider_name == "agno":
        from src.cli.generators.agno import AgnoGenerator

        return AgnoGenerator(token)
    elif provider_name == "copilot":
        from src.cli.generators.copilot import CopilotGenerator

        return CopilotGenerator(token)
    else:
        raise ValueError(f"Provider desconhecido: {provider_name}")


class GeneratorProvider(ABC):
    """Interface base para providers de geração de presets via IA."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Envia prompt para a IA e retorna a resposta.

        Args:
            prompt: Prompt completo com descrição e formato esperado.

        Returns:
            Resposta da IA (JSON string com pipeline, agents e steps).
        """
        ...
