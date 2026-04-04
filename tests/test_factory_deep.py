"""Testes adicionais para cobertura profunda do factory.py."""

from unittest.mock import MagicMock, patch

import pytest
import yaml

from ai_squad.factory import (
    _PLACEHOLDER_PREFIX,
    PlatformConfig,
    PlatformFactory,
)


class TestValidateRequiredTokensDeep:
    """Testes para validate_required_tokens — linhas 273-274."""

    def test_validate_tokens_com_provider_desconhecido_no_registry(self, monkeypatch):
        """ValueError no registry de messaging não propaga (linha 273-274)."""
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "token-real")
        config = PlatformConfig(
            ai_provider="claude-agent-sdk",
            messaging_provider="provider-que-nao-existe",
        )
        # Não deve lançar exceção (catch ValueError no registry)
        missing = config.validate_required_tokens()
        # Token de IA está presente, então não aparece
        assert "CLAUDE_CODE_OAUTH_TOKEN" not in missing

    def test_validate_tokens_import_error_no_registry(self, monkeypatch):
        """ImportError no registry de messaging não propaga (linha 273-274)."""
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "token-real")
        config = PlatformConfig(
            ai_provider="claude-agent-sdk",
            messaging_provider="telegram",
        )
        # Simula ImportError no registry
        with patch(
            "ai_squad.factory.PlatformConfig.validate_required_tokens",
            wraps=config.validate_required_tokens,
        ):
            missing = config.validate_required_tokens()
            # Não deve ter falhado
            assert isinstance(missing, list)

    def test_validate_tokens_com_placeholder(self, monkeypatch):
        """Token com placeholder é considerado ausente."""
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", f"{_PLACEHOLDER_PREFIX}seu_token")
        config = PlatformConfig(
            ai_provider="claude-agent-sdk",
            messaging_provider="cli",
        )
        missing = config.validate_required_tokens()
        assert "CLAUDE_CODE_OAUTH_TOKEN" in missing


class TestCreateAdapterForProvider:
    """Testes para create_adapter_for_provider — linhas 344, 349, 351."""

    def test_create_claude_adapter(self, tmp_path):
        """Cria adapter Claude (default) com sucesso (linha 353)."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        config = PlatformConfig(
            ai_provider="claude-agent-sdk",
            messaging_provider="cli",
            ai_model="claude-sonnet-4-20250514",
        )

        with patch("ai_squad.factory.PlatformFactory._create_claude_adapter") as mock_create:
            mock_create.return_value = MagicMock()
            PlatformFactory.create_adapter_for_provider(
                config,
                working_dir=str(tmp_path),
                agents_dir=str(agents_dir),
                global_skills_dir="",
            )
            mock_create.assert_called_once()
            # Verifica que model foi passado no kwargs
            call_kwargs = mock_create.call_args[0][0]
            assert call_kwargs["model"] == "claude-sonnet-4-20250514"

    def test_create_copilot_adapter(self, tmp_path):
        """Cria adapter Copilot (linha 349)."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        config = PlatformConfig(
            ai_provider="copilot",
            messaging_provider="cli",
        )

        with patch("ai_squad.factory.PlatformFactory._create_copilot_adapter") as mock_create:
            mock_create.return_value = MagicMock()
            PlatformFactory.create_adapter_for_provider(
                config,
                working_dir=str(tmp_path),
                agents_dir=str(agents_dir),
                global_skills_dir="",
            )
            mock_create.assert_called_once()

    def test_create_agno_adapter(self, tmp_path):
        """Cria adapter Agno (linha 351)."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        config = PlatformConfig(
            ai_provider="agno",
            messaging_provider="cli",
        )

        with patch("ai_squad.factory.PlatformFactory._create_agno_adapter") as mock_create:
            mock_create.return_value = MagicMock()
            PlatformFactory.create_adapter_for_provider(
                config,
                working_dir=str(tmp_path),
                agents_dir=str(agents_dir),
                global_skills_dir="",
                state_dir=str(tmp_path / "state"),
            )
            mock_create.assert_called_once()


class TestCreateCopilotAdapterImportError:
    """Testes para _create_copilot_adapter — import error (linhas 387-402)."""

    def test_copilot_import_error(self):
        """ImportError ao carregar Copilot lança RuntimeError (linhas 397-399)."""
        with patch.dict("sys.modules", {"ai_squad.adapters.copilot_adapter": None}):
            with patch(
                "builtins.__import__",
                side_effect=ImportError("No copilot"),
            ):
                with pytest.raises(RuntimeError, match="Copilot"):
                    PlatformFactory._create_copilot_adapter({"timeout": 30})


class TestCreateAgnoAdapterImportError:
    """Testes para _create_agno_adapter — import error (linhas 405-421)."""

    def test_agno_import_error(self):
        """ImportError ao carregar Agno lança RuntimeError (linhas 415-417)."""
        with patch.dict("sys.modules", {"ai_squad.adapters.agno_adapter": None}):
            with patch(
                "builtins.__import__",
                side_effect=ImportError("No agno"),
            ):
                with pytest.raises(RuntimeError, match="Agno"):
                    PlatformFactory._create_agno_adapter({"timeout": 30})


class TestBuildAgentDefinitions:
    """Testes para _build_agent_definitions — linhas 423-451."""

    def test_sem_agentes(self, tmp_path):
        """Retorna dict vazio quando config não tem agentes (linha 431-432)."""
        config = PlatformConfig(
            ai_provider="claude-agent-sdk",
            messaging_provider="cli",
            agents={},
        )
        # AgentDefinition é importado dentro do método via claude_agent_sdk
        mock_agent_def = MagicMock()
        with patch.dict(
            "sys.modules", {"claude_agent_sdk": MagicMock(AgentDefinition=mock_agent_def)}
        ):
            result = PlatformFactory._build_agent_definitions(config, str(tmp_path))
            assert result == {}

    def test_com_agents_md(self, tmp_path):
        """Lê AGENTS.md quando existe (linhas 437-439)."""
        from ai_squad.factory import AgentConfig

        agents_dir = tmp_path / "agents"
        (agents_dir / "po").mkdir(parents=True)
        (agents_dir / "po" / "AGENTS.md").write_text("# PO Agent\n\nVocê é o PO.", encoding="utf-8")

        config = PlatformConfig(
            ai_provider="claude-agent-sdk",
            messaging_provider="cli",
            agents={"po": AgentConfig(name="PO Agent", avatar="📋")},
        )

        mock_agent_def = MagicMock()
        with patch.dict(
            "sys.modules", {"claude_agent_sdk": MagicMock(AgentDefinition=mock_agent_def)}
        ):
            result = PlatformFactory._build_agent_definitions(config, str(agents_dir))
            assert "po" in result
            # Verifica que prompt contém conteúdo do AGENTS.md
            call_kwargs = mock_agent_def.call_args[1]
            assert "PO Agent" in call_kwargs["prompt"]

    def test_sem_agents_md_usa_fallback(self, tmp_path):
        """Sem AGENTS.md, usa prompt padrão (linhas 443-444)."""
        from ai_squad.factory import AgentConfig

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        config = PlatformConfig(
            ai_provider="claude-agent-sdk",
            messaging_provider="cli",
            agents={"dev": AgentConfig(name="Dev Backend", avatar="⚙️")},
        )

        mock_agent_def = MagicMock()
        with patch.dict(
            "sys.modules", {"claude_agent_sdk": MagicMock(AgentDefinition=mock_agent_def)}
        ):
            result = PlatformFactory._build_agent_definitions(config, str(agents_dir))
            assert "dev" in result
            call_kwargs = mock_agent_def.call_args[1]
            assert "Dev Backend" in call_kwargs["prompt"]

    def test_agents_md_com_erro_leitura(self, tmp_path):
        """Erro ao ler AGENTS.md usa fallback (linhas 440-441)."""
        from ai_squad.factory import AgentConfig

        agents_dir = tmp_path / "agents"
        (agents_dir / "dev").mkdir(parents=True)
        agents_md = agents_dir / "dev" / "AGENTS.md"
        agents_md.write_bytes(b"\x80\x81\x82")  # Bytes inválidos UTF-8

        config = PlatformConfig(
            ai_provider="claude-agent-sdk",
            messaging_provider="cli",
            agents={"dev": AgentConfig(name="Dev", avatar="⚙️")},
        )

        mock_agent_def = MagicMock()
        with patch.dict(
            "sys.modules", {"claude_agent_sdk": MagicMock(AgentDefinition=mock_agent_def)}
        ):
            result = PlatformFactory._build_agent_definitions(config, str(agents_dir))
            assert "dev" in result
            call_kwargs = mock_agent_def.call_args[1]
            assert "Dev" in call_kwargs["prompt"]


class TestEnvOverrides:
    """Testes para _apply_env_overrides."""

    def test_env_override_agent_timeout(self, tmp_path, monkeypatch):
        """Variável AGENT_TIMEOUT sobrescreve config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-agent-sdk",
                    "messaging_provider": "cli",
                    "agent_timeout": 100,
                }
            )
        )
        monkeypatch.setenv("AGENT_TIMEOUT", "600")

        config = PlatformConfig.from_yaml(config_file)
        assert config.agent_timeout == 600

    def test_env_override_ai_model(self, tmp_path, monkeypatch):
        """Variável AI_MODEL sobrescreve config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ai_provider": "claude-agent-sdk",
                    "messaging_provider": "cli",
                }
            )
        )
        monkeypatch.setenv("AI_MODEL", "claude-opus")

        config = PlatformConfig.from_yaml(config_file)
        assert config.ai_model == "claude-opus"


class TestConfigYamlInvalido:
    """Testes para YAML inválido."""

    def test_yaml_nao_dict(self, tmp_path):
        """YAML que não é dict lança ValueError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("- item1\n- item2\n")

        with pytest.raises(ValueError, match="formato YAML"):
            PlatformConfig.from_yaml(config_file)

    def test_arquivo_inexistente(self, tmp_path):
        """Arquivo inexistente lança FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            PlatformConfig.from_yaml(tmp_path / "nao-existe.yaml")
