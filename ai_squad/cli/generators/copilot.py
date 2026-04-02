"""Provider de geração via GitHub Copilot SDK."""

import asyncio
import os

import click

from ai_squad.cli.generators.interface import GeneratorProvider


class CopilotGenerator(GeneratorProvider):
    """Gera presets usando o GitHub Copilot SDK.

    Autenticação via `copilot auth login` (CLI) ou GITHUB_TOKEN.
    """

    def __init__(self, token: str = "") -> None:
        try:
            from copilot import CopilotClient  # noqa: F401
        except ImportError:
            click.echo(
                "Erro: SDK Copilot não instalado.\nInstale com: pip install -e '.[copilot]'",
                err=True,
            )
            raise SystemExit(1)

        self._token = token.strip() if token else ""

    def generate(self, prompt: str) -> str:
        """Envia prompt para o Copilot SDK e retorna a resposta."""
        return asyncio.run(self._generate_async(prompt))

    async def _generate_async(self, prompt: str) -> str:
        """Executa a geração via Copilot SDK (async)."""
        from copilot import CopilotClient

        # Auth: token explícito > GITHUB_TOKEN do ambiente > CLI login
        client_opts: dict[str, object] = {}
        github_token = self._token or os.environ.get("GITHUB_TOKEN", "")

        if github_token:
            client_opts["github_token"] = github_token
            client_opts["use_logged_in_user"] = False
        else:
            client_opts["use_logged_in_user"] = True

        try:
            client = CopilotClient(client_opts)
            await client.start()
        except Exception as e:
            error_msg = str(e).lower()
            if "auth" in error_msg or "token" in error_msg or "login" in error_msg:
                click.echo(
                    "Erro: autenticação Copilot não configurada.\n"
                    "Execute 'copilot auth login' ou defina GITHUB_TOKEN.",
                    err=True,
                )
                raise SystemExit(1)
            raise

        try:
            session = await client.create_session({})
            response = await session.send_and_wait({"prompt": prompt}, timeout=120)
            if response and response.data and response.data.content:
                return response.data.content
            return ""
        finally:
            try:
                await client.stop()
            except Exception:
                pass
