"""Registry de agentes com catálogo YAML e matching por domínio."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class AgentEntry:
    """Entrada de um agente no catálogo."""

    name: str
    domain: str
    protocol: str
    tools: list[str]
    version: str
    adapter: str
    path: str
    priority: int = 1


class AgentRegistry:
    """Catálogo de agentes com carregamento YAML e matching por domínio.

    Permite selecionar agentes pelo domínio declarado da feature,
    retornando o mais específico por prioridade.
    """

    def __init__(self) -> None:
        self._agents: list[AgentEntry] = []

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AgentRegistry":
        """Carrega registry a partir de arquivo YAML."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Registry não encontrado: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict) or "agents" not in data:
            raise ValueError("Registry inválido: deve conter campo 'agents'")

        registry = cls()
        for agent_data in data["agents"]:
            entry = AgentEntry(
                name=agent_data["name"],
                domain=agent_data["domain"],
                protocol=agent_data.get("protocol", "text"),
                tools=agent_data.get("tools", []),
                version=agent_data.get("version", "1.0"),
                adapter=agent_data.get("adapter", "claude-code"),
                path=agent_data.get("path", f"agents/{agent_data['name']}"),
                priority=agent_data.get("priority", 1),
            )
            registry._agents.append(entry)

        return registry

    def list_agents(self) -> list[AgentEntry]:
        """Retorna todos os agentes registrados."""
        return list(self._agents)

    def find_by_domain(self, domain: str) -> AgentEntry | None:
        """Encontra agente por domínio, priorizando maior prioridade."""
        matches = [a for a in self._agents if a.domain == domain]
        if not matches:
            return None
        return max(matches, key=lambda a: a.priority)

    def find_by_name(self, name: str) -> AgentEntry | None:
        """Encontra agente por nome."""
        for agent in self._agents:
            if agent.name == name:
                return agent
        return None

    def register(self, entry: AgentEntry) -> None:
        """Registra novo agente no catálogo."""
        self._agents.append(entry)
