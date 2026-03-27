"""Wizard interativo para geração de times via IA."""

from dataclasses import dataclass, field
from pathlib import Path

import click


@dataclass
class WizardResult:
    """Resultado coletado pelo wizard."""

    description: str
    provider: str
    token: str
    messaging: str
    channel_credentials: dict[str, str] = field(default_factory=dict)
    knowledge_enabled: bool = False
    team_name: str = ""


class GenerateWizard:
    """Encapsula o fluxo de perguntas interativas para geração de time."""

    # Credenciais necessárias por canal
    CHANNEL_CREDENTIALS: dict[str, list[tuple[str, str, str]]] = {
        "telegram": [
            ("TELEGRAM_TOKEN", "Bot token do Telegram", "Token criado via @BotFather"),
            ("TELEGRAM_CHAT_ID", "Chat ID do Telegram", "ID do grupo ou chat privado"),
        ],
        "gchat": [
            (
                "GCHAT_CREDENTIALS_PATH",
                "Caminho do credentials JSON do Google Chat",
                "Ex: /path/to/credentials.json",
            ),
            ("GCHAT_SPACE_ID", "Space ID do Google Chat", "ID do space onde o bot atua"),
        ],
        "cli": [],
    }

    def run(self) -> WizardResult:
        """Executa o wizard completo e retorna o resultado."""
        click.echo("\n🤖 ai-squad generate — Criação de time via IA\n")

        description = self._ask_description()
        provider = self._ask_provider()
        token = self._ask_token(provider)
        messaging = self._ask_messaging()
        channel_creds = self._ask_channel_credentials(messaging)
        knowledge = self._ask_knowledge()
        team_name = self._ask_team_name()

        return WizardResult(
            description=description,
            provider=provider,
            token=token,
            messaging=messaging,
            channel_credentials=channel_creds,
            knowledge_enabled=knowledge,
            team_name=team_name,
        )

    def _ask_description(self) -> str:
        """Coleta descrição do time em texto livre."""
        while True:
            description = click.prompt(
                "📝 Descreva o time que você quer criar",
                type=str,
            )
            if description.strip():
                return description.strip()
            click.echo("Erro: descrição não pode ser vazia.", err=True)

    def _ask_provider(self) -> str:
        """Seleção de provider de IA."""
        return click.prompt(
            "🔧 Provider de IA",
            type=click.Choice(["anthropic", "agno", "copilot", "openai"], case_sensitive=False),
            default="anthropic",
        )

    def _ask_token(self, provider: str) -> str:
        """Coleta token do provider sem exibir no terminal."""
        # Copilot: token opcional (auth via CLI)
        if provider == "copilot":
            click.echo(
                "ℹ️  Copilot usa autenticação via CLI (copilot auth login).\n"
                "   Opcionalmente, informe um GITHUB_TOKEN abaixo (Enter para pular)."
            )
            token = click.prompt(
                "🔑 GITHUB_TOKEN (opcional)",
                default="",
                hide_input=True,
                show_default=False,
            )
            return token.strip()

        provider_labels = {
            "anthropic": "Anthropic",
            "agno": "Agno (Google API Key)",
            "openai": "OpenAI",
        }
        label = provider_labels.get(provider, provider)

        while True:
            token = click.prompt(
                f"🔑 Token do {label}",
                hide_input=True,
            )
            if token.strip():
                return token.strip()
            click.echo("Erro: token não pode ser vazio.", err=True)

    def _ask_messaging(self) -> str:
        """Seleção de canal de comunicação."""
        return click.prompt(
            "💬 Canal de comunicação",
            type=click.Choice(["telegram", "gchat", "cli"], case_sensitive=False),
            default="telegram",
        )

    def _ask_channel_credentials(self, messaging: str) -> dict[str, str]:
        """Coleta credenciais específicas do canal escolhido."""
        creds_spec = self.CHANNEL_CREDENTIALS.get(messaging, [])
        if not creds_spec:
            return {}

        credentials: dict[str, str] = {}
        for env_var, label, help_text in creds_spec:
            value = click.prompt(
                f"   {label} ({help_text})",
                hide_input="token" in env_var.lower(),
            )
            credentials[env_var] = value.strip()

        return credentials

    def _ask_knowledge(self) -> bool:
        """Pergunta se deseja habilitar knowledge base."""
        return click.confirm("📚 Habilitar knowledge base?", default=False)

    def _ask_team_name(self) -> str:
        """Coleta nome do time."""
        while True:
            name = click.prompt("📛 Nome do time", type=str)
            name = name.strip()
            if not name:
                click.echo("Erro: nome não pode ser vazio.", err=True)
                continue

            # Verifica se já existe
            squad_dir = Path.cwd() / ".ai-squad"
            if squad_dir.exists():
                click.echo(
                    f"Erro: já existe um time neste diretório (.ai-squad/).\n"
                    f"Remova com: ai-squad remove {name}",
                    err=True,
                )
                continue

            return name
