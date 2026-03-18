"""Parser e modelos para pipeline declarativo.

Lê pipeline.yaml e step files .md para configurar o fluxo
de trabalho de um time de forma agnostica ao framework.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger("ai-dev-team.pipeline")


@dataclass
class QualityCheck:
    """Item individual de um quality gate."""

    description: str
    check_type: str = "semantic"  # file, structural, semantic


@dataclass
class StepConfig:
    """Configuracao de um step do pipeline."""

    id: str
    name: str
    step_type: str = "agent"  # agent, checkpoint
    agent: str = ""
    agents: list[str] = field(default_factory=list)
    execution: str = "subagent"  # subagent, inline, background
    model_tier: str = "powerful"  # fast, powerful
    file: str = ""
    on_reject: str = ""  # step_id para loop de revisao
    max_review_cycles: int = 3
    depends_on: str = ""
    # Parseado do step file .md
    instructions: str = ""
    inputs: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    quality_gate: list[QualityCheck] = field(default_factory=list)
    veto_conditions: list[str] = field(default_factory=list)

    @property
    def all_agents(self) -> list[str]:
        """Retorna todos os agentes do step (singular ou lista)."""
        if self.agents:
            return list(self.agents)
        if self.agent:
            return [self.agent]
        return []

    @property
    def is_checkpoint(self) -> bool:
        """Step é checkpoint (requer aprovação humana)."""
        return self.step_type == "checkpoint"

    @property
    def is_parallel(self) -> bool:
        """Step tem múltiplos agentes em paralelo."""
        return len(self.all_agents) > 1


@dataclass
class PipelineConfig:
    """Configuracao completa de um pipeline."""

    name: str = ""
    steps: list[StepConfig] = field(default_factory=list)
    description: str = ""

    def get_step(self, step_id: str) -> StepConfig | None:
        """Retorna step por ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_step_index(self, step_id: str) -> int:
        """Retorna indice do step. -1 se nao encontrado."""
        for i, step in enumerate(self.steps):
            if step.id == step_id:
                return i
        return -1

    def next_step(self, current_step_id: str) -> StepConfig | None:
        """Retorna proximo step apos o atual."""
        idx = self.get_step_index(current_step_id)
        if idx < 0 or idx >= len(self.steps) - 1:
            return None
        return self.steps[idx + 1]

    @property
    def first_step(self) -> StepConfig | None:
        """Retorna primeiro step do pipeline."""
        return self.steps[0] if self.steps else None

    @property
    def step_ids(self) -> list[str]:
        """Retorna lista de IDs dos steps em ordem."""
        return [s.id for s in self.steps]


class PipelineLoader:
    """Carrega e parseia pipeline.yaml e step files."""

    def __init__(self, pipeline_dir: str | Path) -> None:
        self._pipeline_dir = Path(pipeline_dir)

    def load(self) -> PipelineConfig | None:
        """Carrega pipeline completo do diretório.

        Retorna None se pipeline.yaml nao existe (modo legado).
        """
        yaml_path = self._pipeline_dir / "pipeline.yaml"
        if not yaml_path.exists():
            return None

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            logger.error("Erro ao ler pipeline.yaml: %s", e)
            return None

        if not isinstance(data, dict):
            logger.error("pipeline.yaml invalido: esperado dict")
            return None

        pipeline = PipelineConfig(
            name=data.get("name", ""),
            description=data.get("description", ""),
        )

        # Parseia steps
        steps_data = data.get("pipeline", {}).get("steps", [])
        if not steps_data:
            # Tenta formato alternativo (steps na raiz)
            steps_data = data.get("steps", [])

        for step_data in steps_data:
            step = self._parse_step_config(step_data)
            # Carrega step file se especificado
            if step.file:
                self._load_step_file(step)
            pipeline.steps.append(step)

        logger.info(
            "Pipeline carregado: %s (%d steps)",
            pipeline.name,
            len(pipeline.steps),
        )
        return pipeline

    def _parse_step_config(self, data: dict) -> StepConfig:
        """Parseia configuração de um step do YAML."""
        agents_raw = data.get("agents", [])
        if isinstance(agents_raw, str):
            agents_raw = [agents_raw]

        return StepConfig(
            id=data.get("id", ""),
            name=data.get("name", ""),
            step_type=data.get("type", "agent"),
            agent=data.get("agent", ""),
            agents=agents_raw,
            execution=data.get("execution", "subagent"),
            model_tier=data.get("model_tier", "powerful"),
            file=data.get("file", ""),
            on_reject=data.get("on_reject", ""),
            max_review_cycles=data.get("max_review_cycles", 3),
            depends_on=data.get("depends_on", ""),
        )

    def _load_step_file(self, step: StepConfig) -> None:
        """Carrega e parseia step file .md com frontmatter e seções."""
        step_path = self._pipeline_dir / step.file
        if not step_path.exists():
            logger.warning("Step file nao encontrado: %s", step_path)
            return

        try:
            content = step_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Erro ao ler step file %s: %s", step_path, e)
            return

        # Separa frontmatter (se existir) do corpo — configuração
        # vem do pipeline.yaml, frontmatter é ignorado
        _frontmatter, body = self._parse_frontmatter(content)

        # Parseia seções do body
        step.instructions = body
        step.inputs = self._parse_list_section(body, "Inputs")
        step.expected_outputs = self._parse_list_section(body, "Expected Outputs")
        step.quality_gate = self._parse_quality_gate(body)
        step.veto_conditions = self._parse_list_section(body, "Veto Conditions")

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict, str]:
        """Separa frontmatter YAML do corpo Markdown.

        Retorna (frontmatter_dict, body_text).
        """
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        try:
            frontmatter = yaml.safe_load(parts[1])
            if not isinstance(frontmatter, dict):
                return {}, content
            body = parts[2].strip()
            return frontmatter, body
        except yaml.YAMLError:
            return {}, content

    @staticmethod
    def _parse_list_section(body: str, section_name: str) -> list[str]:
        """Extrai itens de lista de uma seção Markdown.

        Procura por ## Section Name e extrai linhas com - ou - [ ].
        """
        pattern = re.compile(
            rf"##\s+{re.escape(section_name)}\s*\n(.*?)(?=\n##|\Z)",
            re.DOTALL | re.IGNORECASE,
        )
        match = pattern.search(body)
        if not match:
            return []

        section_content = match.group(1)
        items = []
        for line in section_content.splitlines():
            line = line.strip()
            if line.startswith("- "):
                # Remove prefixo de lista e checkbox
                item = re.sub(r"^- (\[[ x]\] )?", "", line).strip()
                if item:
                    items.append(item)

        return items

    @staticmethod
    def _parse_quality_gate(body: str) -> list[QualityCheck]:
        """Extrai quality gate checks de uma seção Markdown.

        Detecta tipo de check automaticamente:
        - Menção a arquivo (existe, tamanho) → file
        - Menção a contagem/formato → structural
        - Resto → semantic (avaliado por LLM)
        """
        items = PipelineLoader._parse_list_section(body, "Quality Gate")
        checks = []

        file_keywords = ("existe", "exists", "ausente", "bytes", "arquivo", "file")
        structural_keywords = (
            "contém",
            "contains",
            "itens",
            "items",
            "formato",
            "format",
            "mínimo",
            "minimum",
            "pelo menos",
            "at least",
        )

        for item in items:
            item_lower = item.lower()
            if any(kw in item_lower for kw in file_keywords):
                check_type = "file"
            elif any(kw in item_lower for kw in structural_keywords):
                check_type = "structural"
            else:
                check_type = "semantic"

            checks.append(QualityCheck(description=item, check_type=check_type))

        return checks
