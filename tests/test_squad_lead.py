"""Testes para Squad Lead e tools do engine."""

import pytest
from unittest.mock import AsyncMock

from src.factory import AgentConfig, SquadLeadConfig, PlatformConfig
from src.orchestrator.tools import AgentResult, DemandStatus, check_workspace


class TestDemandStatus:
    """Testes para DemandStatus."""

    def test_set_result(self):
        """Verifica registro de resultado."""
        status = DemandStatus(demand_id="d-001")
        result = AgentResult(agent_name="po", result="spec pronta")
        status.set_result("po", result)

        assert "po" in status.results
        assert status.results["po"].result == "spec pronta"

    def test_get_summary_vazio(self):
        """Verifica resumo sem resultados."""
        status = DemandStatus(demand_id="d-001")
        summary = status.get_summary()
        assert "Nenhum agente executado" in summary

    def test_get_summary_com_resultados(self):
        """Verifica resumo com resultados."""
        status = DemandStatus(demand_id="d-001")
        status.set_result("po", AgentResult("po", "spec ok", success=True))
        status.set_result("dev", AgentResult("dev", "codigo feito", success=True))

        summary = status.get_summary()
        assert "po" in summary
        assert "dev" in summary
        assert "Concluido" in summary

    def test_get_summary_com_erro(self):
        """Verifica resumo com erro."""
        status = DemandStatus(demand_id="d-001")
        status.set_result("dev", AgentResult("dev", "", success=False, error="timeout"))

        summary = status.get_summary()
        assert "Erro" in summary
        assert "timeout" in summary


class TestCheckWorkspace:
    """Testes para check_workspace."""

    def test_workspace_inexistente(self):
        """Verifica retorno para workspace inexistente."""
        result = check_workspace("/caminho/inexistente")
        assert "nao encontrado" in result

    def test_workspace_existente(self, tmp_path):
        """Verifica retorno para workspace com git."""
        # Inicializa git
        import subprocess
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=str(tmp_path), capture_output=True)

        result = check_workspace(str(tmp_path))
        assert "Git status" in result


class TestAgentConfig:
    """Testes para configuracao de agentes."""

    def test_agent_config_fields(self):
        """Verifica campos do AgentConfig."""
        config = AgentConfig(
            name="PO", avatar="📋",
            command="/po", done_marker="---SPEC_READY---",
        )
        assert config.name == "PO"
        assert config.command == "/po"
        assert config.done_marker == "---SPEC_READY---"

    def test_squad_lead_config_defaults(self):
        """Verifica defaults do SquadLeadConfig."""
        config = SquadLeadConfig()
        assert config.name == "Squad Lead"

    def test_platform_config_agents_alias(self):
        """Verifica que personas e um alias para agents."""
        config = PlatformConfig(
            ai_provider="test",
            messaging_provider="test",
            agents={"po": AgentConfig(name="PO", avatar="📋")},
        )
        assert config.personas == config.agents
        assert "po" in config.personas

    def test_platform_config_from_yaml_agents(self, tmp_path, monkeypatch):
        """Verifica carregamento de agents do YAML."""
        import yaml
        for var in ["AI_PROVIDER", "MESSAGING_PROVIDER", "AGENT_TIMEOUT", "STATE_DIR", "REPO_PATH", "AI_MODEL", "DEV_TIMEOUT"]:
            monkeypatch.delenv(var, raising=False)

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "ai_provider": "claude-agent-sdk",
            "messaging_provider": "telegram",
            "squad_lead": {"name": "Lider", "avatar": "👨‍💼"},
            "agents": {
                "po": {"name": "PO", "avatar": "📋", "command": "/po", "done_marker": "---SPEC_READY---"},
                "dev": {"name": "Dev", "avatar": "🔧", "command": "/dev"},
            },
        }))

        config = PlatformConfig.from_yaml(config_file)
        assert config.squad_lead.name == "Lider"
        assert "po" in config.agents
        assert "dev" in config.agents
        assert config.agents["po"].command == "/po"
        assert config.agents["po"].done_marker == "---SPEC_READY---"

    def test_platform_config_fallback_personas(self, tmp_path, monkeypatch):
        """Verifica fallback de personas para agents."""
        import yaml
        for var in ["AI_PROVIDER", "MESSAGING_PROVIDER", "AGENT_TIMEOUT", "STATE_DIR", "REPO_PATH", "AI_MODEL", "DEV_TIMEOUT"]:
            monkeypatch.delenv(var, raising=False)

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "ai_provider": "claude-code",
            "messaging_provider": "cli",
            "personas": {
                "po": {"name": "PO Antigo", "avatar": "📋"},
            },
        }))

        config = PlatformConfig.from_yaml(config_file)
        assert "po" in config.agents
        assert config.agents["po"].name == "PO Antigo"


class TestEngineAgentsMd:
    """Testes para leitura de AGENTS.md no engine."""

    def test_read_agents_md(self, tmp_path):
        """Verifica leitura de AGENTS.md."""
        from src.orchestrator.engine import OrchestrationEngine
        from src.orchestrator.state import StateManager

        agents_dir = tmp_path / "agents" / "po"
        agents_dir.mkdir(parents=True)
        (agents_dir / "AGENTS.md").write_text("# PO\n## Dominio\nGestao de produto")

        adapter = AsyncMock()
        adapter.on_human_needed = lambda cb: None
        bus = AsyncMock()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))

        engine = OrchestrationEngine(
            adapter, bus, state_mgr,
            workspace=str(tmp_path),
            agents_dir=str(tmp_path / "agents"),
        )

        content = engine._read_agents_md("po")
        assert "Gestao de produto" in content

    def test_read_agents_md_inexistente(self, tmp_path):
        """Verifica retorno vazio para agente inexistente."""
        from src.orchestrator.engine import OrchestrationEngine
        from src.orchestrator.state import StateManager

        adapter = AsyncMock()
        adapter.on_human_needed = lambda cb: None
        bus = AsyncMock()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))

        engine = OrchestrationEngine(
            adapter, bus, state_mgr,
            workspace=str(tmp_path),
            agents_dir=str(tmp_path / "agents"),
        )

        content = engine._read_agents_md("inexistente")
        assert content == ""

    def test_get_agents_summary(self, tmp_path):
        """Verifica geração de resumo de agentes."""
        from src.orchestrator.engine import OrchestrationEngine
        from src.orchestrator.state import StateManager

        agents_dir = tmp_path / "agents" / "po"
        agents_dir.mkdir(parents=True)
        (agents_dir / "AGENTS.md").write_text(
            "# PO\n## Dominio\nGestao de produto\n## Quando Envolver\n- Sempre"
        )

        adapter = AsyncMock()
        adapter.on_human_needed = lambda cb: None
        bus = AsyncMock()
        state_mgr = StateManager(state_dir=str(tmp_path / "state"))
        personas = {"po": AgentConfig(name="PO", avatar="📋")}

        engine = OrchestrationEngine(
            adapter, bus, state_mgr,
            workspace=str(tmp_path),
            personas=personas,
            agents_dir=str(tmp_path / "agents"),
        )

        summary = engine._get_agents_summary()
        assert "PO" in summary
        assert "Gestao de produto" in summary
        assert "Sempre" in summary
