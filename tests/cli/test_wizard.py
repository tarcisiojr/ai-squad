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

    def test_token_vazio_aceito_para_copilot(self) -> None:
        """WizardResult aceita token vazio (copilot sem token)."""
        from src.cli.wizard import WizardResult

        result = WizardResult(
            description="teste",
            provider="copilot",
            token="",
            messaging="cli",
        )
        assert result.token == ""
        assert result.provider == "copilot"

    def test_token_github_aceito_para_copilot(self) -> None:
        """WizardResult aceita GITHUB_TOKEN opcional para copilot."""
        from src.cli.wizard import WizardResult

        result = WizardResult(
            description="teste",
            provider="copilot",
            token="ghp_abc123",
            messaging="cli",
        )
        assert result.token == "ghp_abc123"


class TestWizardCopilotProvider:
    """Testes do wizard com provider copilot."""

    def test_copilot_na_lista_de_providers(self) -> None:
        """Copilot aparece como opção de provider no wizard."""
        from src.cli.wizard import GenerateWizard

        wizard = GenerateWizard()
        # _ask_provider usa click.Choice — verificamos indiretamente
        # que copilot está como opção lendo o código fonte
        import inspect
        source = inspect.getsource(wizard._ask_provider)
        assert "copilot" in source

    def test_ask_token_copilot_aceita_vazio(self) -> None:
        """Token é opcional para copilot (Enter pula)."""
        from src.cli.wizard import GenerateWizard

        wizard = GenerateWizard()
        with patch("click.prompt", return_value=""):
            with patch("click.echo"):
                token = wizard._ask_token("copilot")
        assert token == ""

    def test_ask_token_copilot_aceita_github_token(self) -> None:
        """Copilot aceita GITHUB_TOKEN quando informado."""
        from src.cli.wizard import GenerateWizard

        wizard = GenerateWizard()
        with patch("click.prompt", return_value="ghp_test123"):
            with patch("click.echo"):
                token = wizard._ask_token("copilot")
        assert token == "ghp_test123"
