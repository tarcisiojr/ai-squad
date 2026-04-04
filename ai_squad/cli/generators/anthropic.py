"""Provider de geração via API Anthropic.

Suporta dois modos:
- API key (sk-ant-api...) → SDK anthropic direto
- OAuth token (sk-ant-oat...) → claude-agent-sdk (requer Claude Code CLI)
"""

import asyncio

from ai_squad.cli.generators.interface import GeneratorProvider


def _is_oauth_token(token: str) -> bool:
    """Detecta se o token é OAuth do Claude Code (sk-ant-oatXX-)."""
    return "oat" in token[:20]


class AnthropicGenerator(GeneratorProvider):
    """Gera presets usando API Anthropic ou Claude Code SDK."""

    def __init__(self, token: str) -> None:
        self._token = token

    def generate(self, prompt: str) -> str:
        """Envia prompt para o Claude e retorna a resposta."""
        if _is_oauth_token(self._token):
            return self._generate_with_claude_sdk(prompt)
        return self._generate_with_api_key(prompt)

    def _generate_with_api_key(self, prompt: str) -> str:
        """Autenticação com API key padrão via SDK anthropic."""
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "Pacote 'anthropic' não encontrado. Instale com: pip install anthropic"
            )

        client = anthropic.Anthropic(api_key=self._token)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )

        return "\n".join(block.text for block in message.content if block.type == "text")

    def _generate_with_claude_sdk(self, prompt: str) -> str:
        """Autenticação via OAuth token usando claude-agent-sdk."""
        return asyncio.run(self._query_claude_sdk(prompt))

    async def _query_claude_sdk(self, prompt: str) -> str:
        """Execução assíncrona via claude-agent-sdk."""
        import os

        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        # Injeta o token OAuth como variável de ambiente
        env_backup = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = self._token

        try:
            options = ClaudeAgentOptions(
                permission_mode="bypassPermissions",
                max_turns=1,
                model="claude-haiku-4-5-20251001",
            )

            parts: list[str] = []
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage) and message.result:
                    parts.append(message.result)

            return "\n".join(parts)
        finally:
            # Restaura estado do ambiente
            if env_backup is not None:
                os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = env_backup
            else:
                os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
