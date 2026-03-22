"""Provider de geração via API Anthropic (SDK direto)."""

from src.cli.generators.interface import GeneratorProvider


class AnthropicGenerator(GeneratorProvider):
    """Gera presets usando a API Anthropic diretamente.

    Usa o token informado no wizard para autenticação via SDK,
    sem depender do Claude Code CLI instalado na máquina.
    """

    def __init__(self, token: str) -> None:
        self._token = token

    def generate(self, prompt: str) -> str:
        """Envia prompt para o Claude via API Anthropic e retorna a resposta."""
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "Pacote 'anthropic' não encontrado. "
                "Instale com: pip install anthropic"
            )

        client = anthropic.Anthropic(api_key=self._token)

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )

        # Extrai texto de todos os blocos de conteúdo
        parts = [
            block.text
            for block in message.content
            if block.type == "text"
        ]

        return "\n".join(parts)
