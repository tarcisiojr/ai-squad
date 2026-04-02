"""Testes para interface e mapeamento de providers."""

import pytest

from ai_squad.cli.generators.interface import (
    PROVIDER_CONFIGS,
    GeneratorProvider,
    get_provider,
    get_provider_config,
)


class TestProviderConfig:
    """Testes do mapeamento de configuração por provider."""

    def test_anthropic_config(self) -> None:
        """Configuração do provider Anthropic."""
        config = get_provider_config("anthropic")
        assert config.ai_provider == "claude-agent-sdk"
        assert config.env_var == "CLAUDE_CODE_OAUTH_TOKEN"
        assert "haiku" in config.default_model

    def test_openai_config(self) -> None:
        """Configuração do provider OpenAI."""
        config = get_provider_config("openai")
        assert config.ai_provider == "openai"
        assert config.env_var == "OPENAI_API_KEY"
        assert "gpt" in config.default_model

    def test_agno_config(self) -> None:
        """Configuração do provider Agno."""
        config = get_provider_config("agno")
        assert config.ai_provider == "agno"
        assert config.env_var == "GOOGLE_API_KEY"

    def test_provider_desconhecido_erro(self) -> None:
        """Erro ao buscar provider inexistente."""
        with pytest.raises(ValueError, match="desconhecido"):
            get_provider_config("inexistente")

    def test_copilot_config(self) -> None:
        """Configuração do provider Copilot (sem token, sem modelo fixo)."""
        config = get_provider_config("copilot")
        assert config.ai_provider == "copilot"
        assert config.env_var == ""
        assert config.default_model == ""

    def test_todos_providers_tem_ai_provider(self) -> None:
        """Todos os providers registrados possuem ai_provider definido."""
        for name, config in PROVIDER_CONFIGS.items():
            assert config.ai_provider, f"{name} sem ai_provider"


class TestGetProvider:
    """Testes da factory de providers."""

    def test_provider_desconhecido_erro(self) -> None:
        """Erro ao instanciar provider inexistente."""
        with pytest.raises(ValueError, match="desconhecido"):
            get_provider("inexistente", "fake-token")


class TestGeneratorProviderABC:
    """Testes da interface abstrata."""

    def test_nao_pode_instanciar_abc(self) -> None:
        """Não permite instanciar GeneratorProvider diretamente."""
        with pytest.raises(TypeError):
            GeneratorProvider()  # type: ignore[abstract]
