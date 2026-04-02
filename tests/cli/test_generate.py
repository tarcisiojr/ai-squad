"""Testes para parsing de resposta e criação de estrutura."""

import json

import pytest

from ai_squad.cli.generate import _create_structure, _parse_response
from ai_squad.cli.wizard import WizardResult


# Fixture: JSON de exemplo gerado pela IA
SAMPLE_GENERATED = {
    "pipeline": {
        "name": "Suporte Técnico",
        "description": "Pipeline de suporte técnico automatizado.",
        "steps": [
            {
                "id": "triagem",
                "name": "Triagem",
                "agent": "triager",
                "type": "checkpoint",
                "execution": "subagent",
                "model_tier": "fast",
                "file": "steps/step-01-triagem.md",
            },
            {
                "id": "resolucao",
                "name": "Resolução",
                "agent": "resolver",
                "type": "agent",
                "execution": "subagent",
                "model_tier": "powerful",
                "file": "steps/step-02-resolucao.md",
            },
        ],
    },
    "agents": {
        "triager": {
            "display_name": "Triager",
            "avatar": "🔍",
            "agents_md": "# Triager\n\n## Dominio\nTriagem de tickets.\n",
        },
        "resolver": {
            "display_name": "Resolver",
            "avatar": "🔧",
            "agents_md": "# Resolver\n\n## Dominio\nResolução de problemas.\n",
        },
    },
    "squad_lead_md": "# Squad Lead\n\n## Dominio\nCoordenação.\n",
    "steps": {
        "steps/step-01-triagem.md": "# Step 01: Triagem\n\n## Quality Gate\n- [ ] Ticket classificado\n",
        "steps/step-02-resolucao.md": "# Step 02: Resolução\n\n## Quality Gate\n- [ ] Problema resolvido\n",
    },
}


class TestParseResponse:
    """Testes do parsing de resposta da IA."""

    def test_json_puro(self) -> None:
        """Parseia JSON puro sem markdown."""
        raw = json.dumps(SAMPLE_GENERATED)
        result = _parse_response(raw)
        assert result["pipeline"]["name"] == "Suporte Técnico"

    def test_json_com_markdown(self) -> None:
        """Parseia JSON envolvido em bloco de código markdown."""
        raw = f"```json\n{json.dumps(SAMPLE_GENERATED)}\n```"
        result = _parse_response(raw)
        assert result["pipeline"]["name"] == "Suporte Técnico"

    def test_json_com_texto_antes(self) -> None:
        """Extrai JSON de resposta com texto antes."""
        raw = f"Aqui está o JSON:\n\n{json.dumps(SAMPLE_GENERATED)}"
        result = _parse_response(raw)
        assert "agents" in result

    def test_resposta_invalida_erro(self) -> None:
        """Erro ao parsear resposta sem JSON válido."""
        with pytest.raises(SystemExit):
            _parse_response("Isso não é JSON nenhum.")


class TestCreateStructure:
    """Testes da criação de diretórios e arquivos."""

    def test_estrutura_completa(self, tmp_path) -> None:
        """Cria toda a estrutura de diretórios e arquivos."""
        squad_dir = tmp_path / ".ai-squad"
        result = WizardResult(
            description="Time de suporte",
            provider="anthropic",
            token="fake-token",
            messaging="telegram",
            channel_credentials={
                "TELEGRAM_TOKEN": "bot123",
                "TELEGRAM_CHAT_ID": "456",
            },
            knowledge_enabled=False,
            team_name="MeuTime",
        )

        _create_structure(squad_dir, SAMPLE_GENERATED, result)

        # Diretórios criados
        assert (squad_dir / "state").is_dir()
        assert (squad_dir / "pipeline" / "steps").is_dir()
        assert (squad_dir / "agents" / "triager").is_dir()
        assert (squad_dir / "agents" / "resolver").is_dir()
        assert (squad_dir / "agents" / "squad-lead").is_dir()

        # Arquivos criados
        assert (squad_dir / "pipeline" / "pipeline.yaml").exists()
        assert (squad_dir / "pipeline" / "steps" / "step-01-triagem.md").exists()
        assert (squad_dir / "pipeline" / "steps" / "step-02-resolucao.md").exists()
        assert (squad_dir / "agents" / "triager" / "AGENTS.md").exists()
        assert (squad_dir / "agents" / "squad-lead" / "AGENTS.md").exists()
        assert (squad_dir / "config.yaml").exists()
        assert (squad_dir / ".env").exists()

        # .env tem tokens reais
        env_content = (squad_dir / ".env").read_text()
        assert "fake-token" in env_content
        assert "bot123" in env_content
        assert "456" in env_content
        assert "PREENCHA_AQUI" not in env_content

    def test_knowledge_habilitado(self, tmp_path) -> None:
        """Cria diretório knowledge/ quando habilitado."""
        squad_dir = tmp_path / ".ai-squad"
        result = WizardResult(
            description="Time com knowledge",
            provider="anthropic",
            token="fake-token",
            messaging="cli",
            knowledge_enabled=True,
            team_name="MeuTime",
        )

        _create_structure(squad_dir, SAMPLE_GENERATED, result)

        assert (squad_dir / "knowledge").is_dir()

        # Config deve ter knowledge habilitado
        import yaml

        config = yaml.safe_load((squad_dir / "config.yaml").read_text())
        assert config["knowledge"]["enabled"] is True

    def test_config_agents_populados(self, tmp_path) -> None:
        """Config.yaml contém agentes com name, avatar e command."""
        squad_dir = tmp_path / ".ai-squad"
        result = WizardResult(
            description="Time teste",
            provider="anthropic",
            token="fake-token",
            messaging="cli",
            team_name="MeuTime",
        )

        _create_structure(squad_dir, SAMPLE_GENERATED, result)

        import yaml

        config = yaml.safe_load((squad_dir / "config.yaml").read_text())
        assert "triager" in config["agents"]
        assert config["agents"]["triager"]["name"] == "Triager"
        assert config["agents"]["triager"]["command"] == "/triager"
        assert config["ai_provider"] == "claude-agent-sdk"
