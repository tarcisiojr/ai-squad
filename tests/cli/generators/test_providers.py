"""Testes para providers de geração (mock de SDK)."""

from unittest.mock import MagicMock, patch


class TestAnthropicGenerator:
    """Testes do AnthropicGenerator com API key e OAuth token."""

    @patch.dict("sys.modules", {"anthropic": MagicMock()})
    def test_generate_com_api_key(self) -> None:
        """API key (sk-ant-*) usa SDK Anthropic."""
        import sys

        mock_anthropic = sys.modules["anthropic"]
        mock_client = MagicMock()
        mock_block = MagicMock(type="text", text='{"pipeline": {}}')
        mock_response = MagicMock(content=[mock_block])
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        from src.cli.generators.anthropic import AnthropicGenerator

        gen = AnthropicGenerator("sk-ant-fake-token")
        result = gen.generate("test prompt")

        assert result == '{"pipeline": {}}'
        mock_anthropic.Anthropic.assert_called_once_with(api_key="sk-ant-fake-token")
        mock_client.messages.create.assert_called_once()

    @patch("src.cli.generators.anthropic.httpx")
    def test_generate_com_oauth_token(self, mock_httpx) -> None:
        """OAuth token usa Bearer via httpx."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": '{"pipeline": {}}'}],
        }
        mock_httpx.post.return_value = mock_response

        from src.cli.generators.anthropic import AnthropicGenerator

        gen = AnthropicGenerator("sk-ant-oat01-fake-oauth-token")
        result = gen.generate("test prompt")

        assert result == '{"pipeline": {}}'
        mock_httpx.post.assert_called_once()
        call_kwargs = mock_httpx.post.call_args
        assert "Bearer sk-ant-oat01-fake-oauth-token" in call_kwargs.kwargs["headers"]["Authorization"]

    def test_detecta_oauth_token(self) -> None:
        """Detecta corretamente OAuth token vs API key."""
        from src.cli.generators.anthropic import AnthropicGenerator

        # OAuth tokens contêm "oat" no prefixo
        assert AnthropicGenerator("sk-ant-oat01-abc123")._is_oauth_token() is True
        # API keys padrão não contêm "oat"
        assert AnthropicGenerator("sk-ant-api03-xyz")._is_oauth_token() is False
        assert AnthropicGenerator("some-other-token")._is_oauth_token() is False

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
