"""Provider de geração via OpenAI."""

import click

from src.cli.generators.interface import PROVIDER_CONFIGS, GeneratorProvider


class OpenAIGenerator(GeneratorProvider):
    """Gera presets usando o SDK OpenAI."""

    def __init__(self, token: str) -> None:
        try:
            import openai  # noqa: F401
        except ImportError:
            click.echo(
                "Erro: SDK OpenAI não instalado.\nInstale com: pip install openai",
                err=True,
            )
            raise SystemExit(1)

        self._client = openai.OpenAI(api_key=token)
        self._model = PROVIDER_CONFIGS["openai"].default_model

    def generate(self, prompt: str) -> str:
        """Envia prompt para o GPT e retorna a resposta."""
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
