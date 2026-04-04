"""Testes adicionais para cobertura profunda do generate.py."""

import json
from unittest.mock import MagicMock, patch

import pytest
import yaml

from ai_squad.cli.generate import (
    _default_squad_lead_md,
    _parse_response,
    _show_summary,
    _write_agents,
    _write_config,
    _write_env,
    _write_pipeline,
    _write_steps,
    generate_team,
)
from ai_squad.cli.wizard import WizardResult

# Dados de exemplo para testes
SAMPLE_GENERATED = {
    "pipeline": {
        "name": "Dev Pipeline",
        "description": "Pipeline de desenvolvimento.",
        "steps": [
            {
                "id": "spec",
                "name": "Especificação",
                "agent": "po",
                "type": "agent",
                "execution": "subagent",
                "model_tier": "fast",
                "file": "steps/step-01-spec.md",
            },
            {
                "id": "review",
                "name": "Review",
                "agent": "reviewer",
                "type": "checkpoint",
                "execution": "subagent",
                "model_tier": "powerful",
                "file": "steps/step-02-review.md",
            },
        ],
    },
    "agents": {
        "po": {
            "display_name": "PO Agent",
            "avatar": "📋",
            "agents_md": "# PO\n\n## Dominio\nProduct ownership.\n",
        },
        "reviewer": {
            "display_name": "Reviewer",
            "avatar": "🔍",
        },
    },
    "steps": {
        "steps/step-01-spec.md": "# Especificação\n\n## Quality Gate\n- [ ] Spec pronta\n",
        "step-02-review.md": "# Review\n\n## Quality Gate\n- [ ] Review feito\n",
    },
}


class TestParseResponseDeep:
    """Testes adicionais para _parse_response."""

    def test_json_com_triple_backtick_sem_language(self):
        """JSON envolvido em ``` sem language tag."""
        raw = f"```\n{json.dumps(SAMPLE_GENERATED)}\n```"
        result = _parse_response(raw)
        assert "pipeline" in result

    def test_json_com_texto_antes_e_depois(self):
        """JSON em meio a texto é extraído via regex."""
        raw = f"Aqui está:\n{json.dumps(SAMPLE_GENERATED)}\nFim."
        result = _parse_response(raw)
        assert "agents" in result

    def test_json_invalido_dentro_de_texto(self):
        """Resposta sem JSON válido causa SystemExit."""
        with pytest.raises(SystemExit):
            _parse_response("Texto sem JSON {invalido: true}")


class TestWritePipeline:
    """Testes para _write_pipeline."""

    def test_cria_pipeline_yaml(self, tmp_path):
        """Pipeline.yaml é criado corretamente."""
        squad_dir = tmp_path / ".ai-squad"
        squad_dir.mkdir()

        _write_pipeline(squad_dir, SAMPLE_GENERATED)

        pipeline_path = squad_dir / "pipeline" / "pipeline.yaml"
        assert pipeline_path.exists()
        data = yaml.safe_load(pipeline_path.read_text())
        assert data["name"] == "Dev Pipeline"


class TestWriteSteps:
    """Testes para _write_steps."""

    def test_normaliza_caminho_de_steps(self, tmp_path):
        """Step files com caminho prefixado são normalizados."""
        squad_dir = tmp_path / ".ai-squad"
        (squad_dir / "pipeline" / "steps").mkdir(parents=True)

        _write_steps(squad_dir, SAMPLE_GENERATED)

        # Ambos devem existir — o com "steps/" prefixado e o sem
        assert (squad_dir / "pipeline" / "steps" / "step-01-spec.md").exists()
        assert (squad_dir / "pipeline" / "steps" / "step-02-review.md").exists()


class TestWriteAgents:
    """Testes para _write_agents."""

    def test_agente_sem_agents_md_usa_fallback(self, tmp_path):
        """Agente sem agents_md usa nome como título fallback."""
        squad_dir = tmp_path / ".ai-squad"
        squad_dir.mkdir()

        _write_agents(squad_dir, SAMPLE_GENERATED)

        # Reviewer não tem agents_md definido — deve usar fallback
        reviewer_md = (squad_dir / "agents" / "reviewer" / "AGENTS.md").read_text()
        assert "Reviewer" in reviewer_md

    def test_squad_lead_sempre_criado(self, tmp_path):
        """Squad Lead é sempre criado mesmo sem squad_lead_md."""
        squad_dir = tmp_path / ".ai-squad"
        squad_dir.mkdir()

        # Cria cópia sem squad_lead_md
        generated_sem_sl = {
            "agents": dict(SAMPLE_GENERATED["agents"]),
            "pipeline": SAMPLE_GENERATED["pipeline"],
            "steps": SAMPLE_GENERATED["steps"],
        }

        _write_agents(squad_dir, generated_sem_sl)

        # Squad Lead deve existir com conteúdo padrão
        sl_path = squad_dir / "agents" / "squad-lead" / "AGENTS.md"
        assert sl_path.exists()
        assert "Squad Lead" in sl_path.read_text()


class TestWriteConfig:
    """Testes para _write_config."""

    def test_config_com_knowledge(self, tmp_path):
        """Config.yaml inclui knowledge quando habilitado."""
        squad_dir = tmp_path / ".ai-squad"
        squad_dir.mkdir()

        result = WizardResult(
            description="teste",
            provider="anthropic",
            token="t",
            messaging="cli",
            knowledge_enabled=True,
            team_name="T",
        )

        _write_config(squad_dir, SAMPLE_GENERATED, result)

        config = yaml.safe_load((squad_dir / "config.yaml").read_text())
        assert config["knowledge"]["enabled"] is True

    def test_config_sem_knowledge(self, tmp_path):
        """Config.yaml sem knowledge quando desabilitado."""
        squad_dir = tmp_path / ".ai-squad"
        squad_dir.mkdir()

        result = WizardResult(
            description="teste",
            provider="anthropic",
            token="t",
            messaging="cli",
            knowledge_enabled=False,
            team_name="T",
        )

        _write_config(squad_dir, SAMPLE_GENERATED, result)

        config = yaml.safe_load((squad_dir / "config.yaml").read_text())
        assert "knowledge" not in config


class TestWriteEnv:
    """Testes para _write_env."""

    def test_env_copilot_sem_token(self, tmp_path):
        """Copilot sem token gera comentário de auth via CLI."""
        squad_dir = tmp_path / ".ai-squad"
        squad_dir.mkdir()

        result = WizardResult(
            description="teste",
            provider="copilot",
            token="",
            messaging="cli",
            team_name="T",
        )

        _write_env(squad_dir, result)

        env_content = (squad_dir / ".env").read_text()
        assert "copilot auth login" in env_content.lower() or "GITHUB_TOKEN" in env_content

    def test_env_copilot_com_github_token(self, tmp_path):
        """Copilot com token GitHub gera variável GITHUB_TOKEN."""
        squad_dir = tmp_path / ".ai-squad"
        squad_dir.mkdir()

        result = WizardResult(
            description="teste",
            provider="copilot",
            token="ghp_abc123",
            messaging="cli",
            team_name="T",
        )

        _write_env(squad_dir, result)

        env_content = (squad_dir / ".env").read_text()
        assert "ghp_abc123" in env_content

    def test_env_com_credenciais_de_canal(self, tmp_path):
        """Credenciais do canal de mensageria são incluídas."""
        squad_dir = tmp_path / ".ai-squad"
        squad_dir.mkdir()

        result = WizardResult(
            description="teste",
            provider="anthropic",
            token="tk",
            messaging="telegram",
            channel_credentials={
                "TELEGRAM_TOKEN": "bot123",
                "TELEGRAM_CHAT_ID": "456",
            },
            team_name="T",
        )

        _write_env(squad_dir, result)

        env_content = (squad_dir / ".env").read_text()
        assert "bot123" in env_content
        assert "456" in env_content
        assert "TELEGRAM" in env_content


class TestShowSummary:
    """Testes para _show_summary."""

    def test_exibe_resumo(self, capsys):
        """Exibe resumo com agentes, pipeline e checkpoints."""
        _show_summary(SAMPLE_GENERATED, "MeuTime")

        captured = capsys.readouterr()
        assert "MeuTime" in captured.out
        assert "po" in captured.out
        assert "Review" in captured.out or "Especificação" in captured.out


class TestDefaultSquadLeadMd:
    """Testes para _default_squad_lead_md."""

    def test_conteudo_padrao(self):
        """Conteúdo padrão inclui seções obrigatórias."""
        md = _default_squad_lead_md()
        assert "# Squad Lead" in md
        assert "Dominio" in md
        assert "Responsabilidades" in md
        assert "Restricoes" in md


class TestGenerateTeam:
    """Testes para generate_team (fluxo completo)."""

    def test_generate_team_completo(self, tmp_path, monkeypatch):
        """Fluxo completo de geração do time."""
        monkeypatch.chdir(tmp_path)

        mock_provider = MagicMock()
        mock_provider.generate.return_value = json.dumps(SAMPLE_GENERATED)

        result = WizardResult(
            description="Time de desenvolvimento",
            provider="anthropic",
            token="fake-token",
            messaging="cli",
            team_name="TestTeam",
        )

        with (
            patch("ai_squad.cli.generate.get_provider", return_value=mock_provider),
            patch("ai_squad.cli.generate.click.echo"),
        ):
            squad_dir = generate_team(result)

        assert squad_dir.exists()
        assert (squad_dir / "config.yaml").exists()
        assert (squad_dir / "pipeline" / "pipeline.yaml").exists()
