"""Testes para providers de geração (mock de SDK)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAnthropicGenerator:
    """Testes do AnthropicGenerator com mock do claude-agent-sdk."""

    @patch("src.cli.generators.anthropic.asyncio")
    def test_generate_chama_query(self, mock_asyncio) -> None:
        """Verifica que generate usa asyncio.run internamente."""
        mock_asyncio.run.return_value = '{"pipeline": {}}'

        from src.cli.generators.anthropic import AnthropicGenerator

        gen = AnthropicGenerator("fake-token")
        result = gen.generate("test prompt")

        assert result == '{"pipeline": {}}'
        mock_asyncio.run.assert_called_once()

    def test_token_guardado(self) -> None:
        """Token é armazenado para uso no .env."""
        from src.cli.generators.anthropic import AnthropicGenerator

        gen = AnthropicGenerator("meu-token-123")
        assert gen._token == "meu-token-123"


class TestOpenAIGenerator:
    """Testes do OpenAIGenerator com mock do SDK."""

    @patch.dict("sys.modules", {"openai": MagicMock()})
    def test_generate_chama_api(self) -> None:
        """Verifica chamada correta à API OpenAI."""
        import sys

        mock_openai = sys.modules["openai"]
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"pipeline": {}}'))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        from src.cli.generators.openai import OpenAIGenerator

        gen = OpenAIGenerator("fake-token")
        result = gen.generate("test prompt")

        assert result == '{"pipeline": {}}'
        mock_client.chat.completions.create.assert_called_once()
