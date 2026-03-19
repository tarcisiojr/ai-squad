"""Testes para o wizard interativo de geração."""

from unittest.mock import patch

from click.testing import CliRunner

from src.cli.main import cli


class TestGenerateWizard:
    """Testes do wizard via CliRunner."""

    def test_comando_generate_existe(self) -> None:
        """Comando generate está registrado no CLI."""
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0
        assert "linguagem natural" in result.output.lower() or "IA" in result.output

    def test_cancelamento_com_ctrl_c(self) -> None:
        """Ctrl+C cancela o wizard graciosamente."""
        runner = CliRunner()
        result = runner.invoke(cli, ["generate"], input="\x03")
        # Não deve dar traceback
        assert result.exit_code == 0 or "cancelada" in (result.output or "").lower()


class TestWizardResult:
    """Testes do dataclass WizardResult."""

    def test_valores_default(self) -> None:
        """Valores default do WizardResult."""
        from src.cli.wizard import WizardResult

        result = WizardResult(
            description="teste",
            provider="anthropic",
            token="tk",
            messaging="cli",
        )
        assert result.channel_credentials == {}
        assert result.knowledge_enabled is False
        assert result.team_name == ""

    def test_channel_credentials_preenchido(self) -> None:
        """Channel credentials aceita dict."""
        from src.cli.wizard import WizardResult

        result = WizardResult(
            description="teste",
            provider="anthropic",
            token="tk",
            messaging="telegram",
            channel_credentials={"TELEGRAM_TOKEN": "bot123"},
        )
        assert result.channel_credentials["TELEGRAM_TOKEN"] == "bot123"
