"""Testes para providers de geração (mock de SDK)."""

import pytest
from unittest.mock import MagicMock, patch


class TestAnthropicGenerator:
    """Testes do AnthropicGenerator com API key e OAuth token."""

    @patch.dict("sys.modules", {"anthropic": MagicMock()})
    def test_generate_com_api_key(self) -> None:
        """API key (sk-ant-api*) usa SDK Anthropic."""
        import sys

        mock_anthropic = sys.modules["anthropic"]
        mock_client = MagicMock()
        mock_block = MagicMock(type="text", text='{"pipeline": {}}')
        mock_response = MagicMock(content=[mock_block])
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        from ai_squad.cli.generators.anthropic import AnthropicGenerator

        gen = AnthropicGenerator("sk-ant-api03-fake-token")
        result = gen.generate("test prompt")

        assert result == '{"pipeline": {}}'
        mock_anthropic.Anthropic.assert_called_once_with(api_key="sk-ant-api03-fake-token")

    @patch("ai_squad.cli.generators.anthropic.asyncio")
    def test_generate_com_oauth_token(self, mock_asyncio) -> None:
        """OAuth token (sk-ant-oat*) usa claude-agent-sdk."""
        mock_asyncio.run.return_value = '{"pipeline": {}}'

        from ai_squad.cli.generators.anthropic import AnthropicGenerator

        gen = AnthropicGenerator("sk-ant-oat01-fake-oauth-token")
        result = gen.generate("test prompt")

        assert result == '{"pipeline": {}}'
        mock_asyncio.run.assert_called_once()

    def test_detecta_oauth_token(self) -> None:
        """Detecta corretamente OAuth token vs API key."""
        from ai_squad.cli.generators.anthropic import _is_oauth_token

        assert _is_oauth_token("sk-ant-oat01-abc123") is True
        assert _is_oauth_token("sk-ant-api03-xyz") is False
        assert _is_oauth_token("some-other-token") is False

    def test_token_guardado(self) -> None:
        """Token é armazenado para uso no .env."""
        from ai_squad.cli.generators.anthropic import AnthropicGenerator

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

        from ai_squad.cli.generators.openai import OpenAIGenerator

        gen = OpenAIGenerator("fake-token")
        result = gen.generate("test prompt")

        assert result == '{"pipeline": {}}'
        mock_client.chat.completions.create.assert_called_once()


class TestCopilotGenerator:
    """Testes do CopilotGenerator com mock do SDK."""

    def test_sdk_nao_instalado_exibe_mensagem(self) -> None:
        """Sem copilot-sdk instalado, exibe mensagem de instalação."""
        with patch.dict("sys.modules", {"copilot": None}):
            with pytest.raises(SystemExit):
                from importlib import reload
                import ai_squad.cli.generators.copilot as mod
                reload(mod)
                mod.CopilotGenerator()

    @patch.dict("sys.modules", {"copilot": MagicMock()})
    def test_token_armazenado(self) -> None:
        """Token é armazenado para uso na autenticação."""
        from ai_squad.cli.generators.copilot import CopilotGenerator

        gen = CopilotGenerator("meu-github-token")
        assert gen._token == "meu-github-token"

    @patch.dict("sys.modules", {"copilot": MagicMock()})
    def test_token_vazio_aceito(self) -> None:
        """Token vazio é aceito (auth via CLI)."""
        from ai_squad.cli.generators.copilot import CopilotGenerator

        gen = CopilotGenerator("")
        assert gen._token == ""

    @patch("ai_squad.cli.generators.copilot.asyncio")
    @patch.dict("sys.modules", {"copilot": MagicMock()})
    def test_generate_chama_asyncio_run(self, mock_asyncio) -> None:
        """Generate delega para asyncio.run."""
        mock_asyncio.run.return_value = '{"pipeline": {}}'

        from ai_squad.cli.generators.copilot import CopilotGenerator

        gen = CopilotGenerator()
        result = gen.generate("test prompt")

        assert result == '{"pipeline": {}}'
        mock_asyncio.run.assert_called_once()

    @patch.dict("sys.modules", {"copilot": MagicMock()})
    def test_get_provider_retorna_copilot_generator(self) -> None:
        """get_provider('copilot') retorna CopilotGenerator."""
        from ai_squad.cli.generators.copilot import CopilotGenerator
        from ai_squad.cli.generators.interface import get_provider

        provider = get_provider("copilot", "")
        assert isinstance(provider, CopilotGenerator)
