"""Provider de geração via Claude (claude-agent-sdk)."""

import asyncio

from src.cli.generators.interface import GeneratorProvider


class AnthropicGenerator(GeneratorProvider):
    """Gera presets usando o claude-agent-sdk (query one-shot).

    Usa a autenticação já configurada no Claude Code do usuário.
    O token informado no wizard é salvo no .env do time, não usado aqui.
    """

    def __init__(self, token: str) -> None:
        # Token guardado para salvar no .env do time
        self._token = token

    def generate(self, prompt: str) -> str:
        """Envia prompt para o Claude via claude-agent-sdk e retorna a resposta."""
        return asyncio.run(self._generate_async(prompt))

    async def _generate_async(self, prompt: str) -> str:
        """Execução assíncrona da query."""
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        options = ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            max_turns=1,
            model="claude-haiku-4-5-20251001",
        )

        parts: list[str] = []
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                parts.append(message.result)

        return "\n".join(parts)
