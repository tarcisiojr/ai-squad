"""Coletor de contexto do produto para injeção nos prompts dos agentes."""

import time
from pathlib import Path


class ProductContextCollector:
    """Coleta contexto do repositório alvo para enriquecer prompts.

    Lê README.md, estrutura de diretórios e specs existentes
    para que os agentes entendam o produto antes de agir.
    Usa cache com TTL para evitar leituras de disco repetidas.
    """

    MAX_README_CHARS = 4000
    MAX_CLAUDE_MD_CHARS = 6000
    MAX_TREE_DEPTH = 2
    CACHE_TTL = 60  # segundos — recarrega do disco a cada 60s

    def __init__(self, workspace: str = "/workspace") -> None:
        self._workspace = Path(workspace)
        self._cache: dict[str, tuple[float, str]] = {}  # key → (timestamp, content)

    def collect(self, submodule_path: str = "") -> str:
        """Coleta todo o contexto disponível e retorna como texto formatado.

        Usa cache com TTL para evitar leituras de disco repetidas.

        Args:
            submodule_path: Caminho relativo do submodulo (ex: "packages/api").
                          Se informado, carrega tambem o AGENTS.md do submodulo.
        """
        cache_key = f"ctx:{submodule_path}"
        cached = self._cache.get(cache_key)
        if cached:
            ts, content = cached
            if time.time() - ts < self.CACHE_TTL:
                return content

        partes = []

        claude_md = self._read_claude_md()
        if claude_md:
            partes.append(claude_md)

        if submodule_path:
            submodule_md = self._read_submodule_agents_md(submodule_path)
            if submodule_md:
                partes.append(submodule_md)

        readme = self._read_readme()
        if readme:
            partes.append(readme)

        tree = self._read_tree()
        if tree:
            partes.append(tree)

        specs = self._read_existing_specs()
        if specs:
            partes.append(specs)

        result = "\n\n".join(partes) if partes else ""
        self._cache[cache_key] = (time.time(), result)
        return result

    def _read_claude_md(self) -> str:
        """Le o CLAUDE.md do workspace raiz (regras do projeto guarda-chuva)."""
        for name in ("CLAUDE.md", "AGENTS.md"):
            path = self._workspace / name
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    if len(content) > self.MAX_CLAUDE_MD_CHARS:
                        content = content[: self.MAX_CLAUDE_MD_CHARS] + "\n\n[truncado]"
                    return f"### Regras do Projeto (raiz)\n\n{content}"
                except (OSError, UnicodeDecodeError):
                    pass
        return ""

    def _read_submodule_agents_md(self, submodule_path: str) -> str:
        """Le o AGENTS.md de um submodulo especifico."""
        sub_dir = self._workspace / submodule_path
        if not sub_dir.exists():
            return ""

        for name in ("CLAUDE.md", "AGENTS.md"):
            path = sub_dir / name
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    if len(content) > self.MAX_CLAUDE_MD_CHARS:
                        content = content[: self.MAX_CLAUDE_MD_CHARS] + "\n\n[truncado]"
                    return f"### Regras do Submodulo ({submodule_path})\n\n{content}"
                except (OSError, UnicodeDecodeError):
                    pass
        return ""

    def _read_readme(self) -> str:
        """Lê o README.md do workspace."""
        readme_path = self._workspace / "README.md"
        if not readme_path.exists():
            return ""

        try:
            content = readme_path.read_text(encoding="utf-8")
            if len(content) > self.MAX_README_CHARS:
                content = content[: self.MAX_README_CHARS] + "\n\n[truncado]"
            return f"### README.md\n\n{content}"
        except (OSError, UnicodeDecodeError):
            return ""

    def _read_tree(self) -> str:
        """Gera árvore de diretórios do workspace até 2 níveis."""
        if not self._workspace.exists():
            return ""

        lines = []
        self._walk_tree(self._workspace, lines, depth=0)

        if not lines:
            return ""

        return "### Estrutura do projeto\n\n```\n" + "\n".join(lines) + "\n```"

    def _walk_tree(self, path: Path, lines: list[str], depth: int) -> None:
        """Percorre diretórios recursivamente até profundidade máxima."""
        if depth > self.MAX_TREE_DEPTH:
            return

        # Diretórios e arquivos a ignorar
        ignore = {
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            ".tox",
            ".mypy_cache",
            ".pytest_cache",
            "dist",
            "build",
            ".eggs",
            "*.egg-info",
        }

        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return

        for entry in entries:
            if entry.name in ignore or entry.name.startswith("."):
                continue

            prefix = "  " * depth
            if entry.is_dir():
                lines.append(f"{prefix}{entry.name}/")
                self._walk_tree(entry, lines, depth + 1)
            else:
                lines.append(f"{prefix}{entry.name}")

    def _read_existing_specs(self) -> str:
        """Lê specs de demandas anteriores."""
        specs_dir = self._workspace / "specs"
        if not specs_dir.exists() or not specs_dir.is_dir():
            return ""

        demandas = []
        for demand_dir in sorted(specs_dir.iterdir()):
            if not demand_dir.is_dir():
                continue

            proposal = demand_dir / "proposal.md"
            titulo = demand_dir.name
            if proposal.exists():
                try:
                    content = proposal.read_text(encoding="utf-8")
                    # Extrai primeiro parágrafo como resumo
                    for line in content.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and not line.startswith("<!--"):
                            titulo = f"{demand_dir.name}: {line[:100]}"
                            break
                except (OSError, UnicodeDecodeError):
                    pass

            demandas.append(f"- {titulo}")

        if not demandas:
            return ""

        return "### Demandas anteriores\n\n" + "\n".join(demandas)
