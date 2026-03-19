"""Provider de geração via Agno (Google Gemini)."""

import click

from src.cli.generators.interface import PROVIDER_CONFIGS, GeneratorProvider


class AgnoGenerator(GeneratorProvider):
    """Gera presets usando o SDK Agno."""

    def __init__(self, token: str) -> None:
        try:
            import agno  # noqa: F401
        except ImportError:
            click.echo(
                "Erro: SDK Agno não instalado.\nInstale com: pip install agno",
                err=True,
            )
            raise SystemExit(1)

        self._token = token
        self._model = PROVIDER_CONFIGS["agno"].default_model

    def generate(self, prompt: str) -> str:
        """Envia prompt para o Gemini via Agno e retorna a resposta."""
        import os

        from agno.agent import Agent
        from agno.models.google import Gemini

        # Agno usa env var para autenticação
        original = os.environ.get("GOOGLE_API_KEY")
        os.environ["GOOGLE_API_KEY"] = self._token
        try:
            agent = Agent(model=Gemini(id=self._model))
            response = agent.run(prompt)
            return response.content
        finally:
            if original is not None:
                os.environ["GOOGLE_API_KEY"] = original
            else:
                os.environ.pop("GOOGLE_API_KEY", None)
