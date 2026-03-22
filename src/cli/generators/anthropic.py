"""Provider de geração via API Anthropic (SDK ou OAuth)."""

import httpx

from src.cli.generators.interface import GeneratorProvider

# Configuração compartilhada
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 8192
_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_TIMEOUT = 120


class AnthropicGenerator(GeneratorProvider):
    """Gera presets usando a API Anthropic diretamente.

    Suporta dois tipos de token:
    - API key (sk-ant-...) → autenticação via x-api-key
    - OAuth token do Claude Code → autenticação via Bearer
    """

    def __init__(self, token: str) -> None:
        self._token = token

    def _is_oauth_token(self) -> bool:
        """Detecta se o token é OAuth do Claude Code (sk-ant-oatXX-)."""
        return "oat" in self._token[:20]

    def generate(self, prompt: str) -> str:
        """Envia prompt para o Claude e retorna a resposta."""
        if self._is_oauth_token():
            return self._generate_with_oauth(prompt)
        return self._generate_with_api_key(prompt)

    def _generate_with_api_key(self, prompt: str) -> str:
        """Autenticação com API key padrão via SDK."""
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "Pacote 'anthropic' não encontrado. "
                "Instale com: pip install anthropic"
            )

        client = anthropic.Anthropic(api_key=self._token)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )

        return "\n".join(
            block.text for block in message.content if block.type == "text"
        )

    def _generate_with_oauth(self, prompt: str) -> str:
        """Autenticação com OAuth token do Claude Code via Bearer."""
        response = httpx.post(
            _API_URL,
            headers={
                "Authorization": f"Bearer {self._token}",
                "anthropic-version": _API_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": _MODEL,
                "max_tokens": _MAX_TOKENS,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        return "\n".join(
            block["text"] for block in data["content"] if block["type"] == "text"
        )
