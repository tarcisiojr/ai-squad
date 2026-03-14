"""Testes para o registry de agentes."""

import pytest
import yaml

from src.registry.registry import AgentRegistry, AgentEntry


class TestAgentRegistry:
    """Testes para AgentRegistry."""

    @pytest.fixture
    def registry_file(self, tmp_path):
        """Cria arquivo registry.yaml de teste."""
        data = {
            "agents": [
                {
                    "name": "po",
                    "domain": "product",
                    "protocol": "text",
                    "tools": [],
                    "version": "1.0",
                    "adapter": "claude-code",
                    "path": "agents/po",
                    "priority": 1,
                },
                {
                    "name": "dev-web",
                    "domain": "web",
                    "protocol": "text",
                    "tools": ["html", "css", "javascript"],
                    "version": "1.0",
                    "adapter": "claude-code",
                    "path": "agents/dev-web",
                    "priority": 2,
                },
                {
                    "name": "dev-web-senior",
                    "domain": "web",
                    "protocol": "text",
                    "tools": ["html", "css", "javascript", "react"],
                    "version": "2.0",
                    "adapter": "claude-code",
                    "path": "agents/dev-web-senior",
                    "priority": 5,
                },
            ]
        }
        file = tmp_path / "registry.yaml"
        file.write_text(yaml.dump(data))
        return file

    def test_carregamento_yaml(self, registry_file):
        """Verifica carregamento do registry a partir de YAML."""
        registry = AgentRegistry.from_yaml(registry_file)
        agents = registry.list_agents()
        assert len(agents) == 3

    def test_arquivo_nao_encontrado(self):
        """Verifica erro quando arquivo não existe."""
        with pytest.raises(FileNotFoundError):
            AgentRegistry.from_yaml("/caminho/inexistente.yaml")

    def test_yaml_invalido(self, tmp_path):
        """Verifica erro quando YAML é inválido."""
        file = tmp_path / "registry.yaml"
        file.write_text("apenas uma string")
        with pytest.raises(ValueError, match="agents"):
            AgentRegistry.from_yaml(file)

    def test_find_by_domain(self, registry_file):
        """Verifica busca de agente por domínio."""
        registry = AgentRegistry.from_yaml(registry_file)
        agent = registry.find_by_domain("product")
        assert agent is not None
        assert agent.name == "po"

    def test_find_by_domain_prioridade(self, registry_file):
        """Verifica que retorna agente de maior prioridade para o domínio."""
        registry = AgentRegistry.from_yaml(registry_file)
        agent = registry.find_by_domain("web")
        assert agent is not None
        assert agent.name == "dev-web-senior"
        assert agent.priority == 5

    def test_find_by_domain_inexistente(self, registry_file):
        """Verifica que retorna None para domínio inexistente."""
        registry = AgentRegistry.from_yaml(registry_file)
        agent = registry.find_by_domain("mobile")
        assert agent is None

    def test_find_by_name(self, registry_file):
        """Verifica busca de agente por nome."""
        registry = AgentRegistry.from_yaml(registry_file)
        agent = registry.find_by_name("dev-web")
        assert agent is not None
        assert agent.domain == "web"

    def test_find_by_name_inexistente(self, registry_file):
        """Verifica que retorna None para nome inexistente."""
        registry = AgentRegistry.from_yaml(registry_file)
        agent = registry.find_by_name("inexistente")
        assert agent is None

    def test_extensibilidade_registro_dinamico(self, registry_file):
        """Verifica que novos agentes podem ser registrados dinamicamente."""
        registry = AgentRegistry.from_yaml(registry_file)
        novo_agente = AgentEntry(
            name="dev-data",
            domain="data",
            protocol="text",
            tools=["python", "pandas", "sql"],
            version="1.0",
            adapter="claude-code",
            path="agents/dev-data",
            priority=3,
        )
        registry.register(novo_agente)

        encontrado = registry.find_by_domain("data")
        assert encontrado is not None
        assert encontrado.name == "dev-data"
        assert len(registry.list_agents()) == 4

    def test_agent_entry_campos(self, registry_file):
        """Verifica que todos os campos são carregados corretamente."""
        registry = AgentRegistry.from_yaml(registry_file)
        agent = registry.find_by_name("dev-web")
        assert agent.name == "dev-web"
        assert agent.domain == "web"
        assert agent.protocol == "text"
        assert "html" in agent.tools
        assert agent.version == "1.0"
        assert agent.adapter == "claude-code"
        assert agent.path == "agents/dev-web"
        assert agent.priority == 2
