"""Testes para o parser de pipeline declarativo."""

import pytest
import yaml

from ai_squad.orchestrator.pipeline import (
    PipelineConfig,
    PipelineLoader,
    StepConfig,
)

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_step(step_id: str, **kwargs) -> StepConfig:
    """Cria StepConfig com valores padrão para testes."""
    return StepConfig(id=step_id, name=kwargs.pop("name", step_id), **kwargs)


def _make_pipeline(*steps: StepConfig, name: str = "test") -> PipelineConfig:
    """Cria PipelineConfig com lista de steps."""
    return PipelineConfig(name=name, steps=list(steps))


def _write_pipeline_yaml(base_dir, data: dict) -> None:
    """Escreve pipeline.yaml no diretório informado."""
    path = base_dir / "pipeline.yaml"
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


def _write_step_file(base_dir, filename: str, content: str) -> None:
    """Escreve step file .md no diretório informado."""
    path = base_dir / filename
    path.write_text(content, encoding="utf-8")


# ── TestStepConfig ───────────────────────────────────────────────────────


class TestStepConfig:
    """Testes para propriedades de StepConfig."""

    def test_all_agents_com_agente_unico(self):
        """Retorna lista com agente singular quando 'agent' definido."""
        step = _make_step("s1", agent="dev-backend")
        assert step.all_agents == ["dev-backend"]

    def test_all_agents_com_lista_de_agentes(self):
        """Retorna lista de agentes quando 'agents' definido."""
        step = _make_step("s1", agents=["dev-backend", "dev-frontend"])
        assert step.all_agents == ["dev-backend", "dev-frontend"]

    def test_all_agents_prioriza_agents_sobre_agent(self):
        """Quando ambos definidos, 'agents' tem prioridade."""
        step = _make_step("s1", agent="po", agents=["dev-backend", "dev-frontend"])
        assert step.all_agents == ["dev-backend", "dev-frontend"]

    def test_all_agents_vazio_sem_agente(self):
        """Retorna lista vazia quando nenhum agente definido."""
        step = _make_step("s1")
        assert step.all_agents == []

    def test_is_checkpoint_verdadeiro(self):
        """Step com type checkpoint retorna True."""
        step = _make_step("s1", step_type="checkpoint")
        assert step.is_checkpoint is True

    def test_is_checkpoint_falso_para_agent(self):
        """Step com type agent retorna False."""
        step = _make_step("s1", step_type="agent")
        assert step.is_checkpoint is False

    def test_is_parallel_verdadeiro(self):
        """Step com múltiplos agentes é paralelo."""
        step = _make_step("s1", agents=["dev-backend", "dev-frontend"])
        assert step.is_parallel is True

    def test_is_parallel_falso_com_um_agente(self):
        """Step com agente único não é paralelo."""
        step = _make_step("s1", agent="dev-backend")
        assert step.is_parallel is False


# ── TestPipelineConfig ───────────────────────────────────────────────────


class TestPipelineConfig:
    """Testes para métodos de navegação do PipelineConfig."""

    @pytest.fixture
    def pipeline(self):
        """Pipeline com 3 steps para testes de navegação."""
        return _make_pipeline(
            _make_step("planejamento", agent="po"),
            _make_step("desenvolvimento", agents=["dev-backend", "dev-frontend"]),
            _make_step("revisao", agent="code-review"),
        )

    def test_get_step_por_id(self, pipeline):
        """Retorna step correto pelo ID."""
        step = pipeline.get_step("desenvolvimento")
        assert step is not None
        assert step.id == "desenvolvimento"

    def test_get_step_inexistente_retorna_none(self, pipeline):
        """Retorna None para ID inexistente."""
        assert pipeline.get_step("inexistente") is None

    def test_get_step_index(self, pipeline):
        """Retorna índice correto do step."""
        assert pipeline.get_step_index("planejamento") == 0
        assert pipeline.get_step_index("desenvolvimento") == 1
        assert pipeline.get_step_index("revisao") == 2

    def test_get_step_index_inexistente(self, pipeline):
        """Retorna -1 para step inexistente."""
        assert pipeline.get_step_index("inexistente") == -1

    def test_next_step_retorna_proximo(self, pipeline):
        """Retorna step seguinte ao atual."""
        next_s = pipeline.next_step("planejamento")
        assert next_s is not None
        assert next_s.id == "desenvolvimento"

    def test_next_step_retorna_none_para_ultimo(self, pipeline):
        """Retorna None quando não há próximo step."""
        assert pipeline.next_step("revisao") is None

    def test_next_step_retorna_none_para_inexistente(self, pipeline):
        """Retorna None para step inexistente."""
        assert pipeline.next_step("inexistente") is None

    def test_first_step(self, pipeline):
        """Retorna primeiro step do pipeline."""
        first = pipeline.first_step
        assert first is not None
        assert first.id == "planejamento"

    def test_first_step_pipeline_vazio(self):
        """Retorna None para pipeline sem steps."""
        pipeline = PipelineConfig(name="vazio")
        assert pipeline.first_step is None

    def test_step_ids(self, pipeline):
        """Retorna lista ordenada de IDs."""
        assert pipeline.step_ids == [
            "planejamento",
            "desenvolvimento",
            "revisao",
        ]


# ── TestPipelineLoader ───────────────────────────────────────────────────


class TestPipelineLoader:
    """Testes para carregamento e parsing de pipeline."""

    def test_carrega_pipeline_valido(self, tmp_path):
        """Carrega pipeline.yaml com steps corretamente."""
        _write_pipeline_yaml(
            tmp_path,
            {
                "name": "Meu Pipeline",
                "description": "Pipeline de teste",
                "pipeline": {
                    "steps": [
                        {"id": "plan", "name": "Planejamento", "agent": "po"},
                        {"id": "dev", "name": "Desenvolvimento", "agent": "dev-backend"},
                    ],
                },
            },
        )

        loader = PipelineLoader(tmp_path)
        pipeline = loader.load()

        assert pipeline is not None
        assert pipeline.name == "Meu Pipeline"
        assert pipeline.description == "Pipeline de teste"
        assert len(pipeline.steps) == 2
        assert pipeline.steps[0].id == "plan"
        assert pipeline.steps[1].agent == "dev-backend"

    def test_carrega_steps_na_raiz(self, tmp_path):
        """Carrega steps quando definidos na raiz do YAML (formato alternativo)."""
        _write_pipeline_yaml(
            tmp_path,
            {
                "name": "Alt",
                "steps": [
                    {"id": "s1", "name": "Step 1", "agent": "po"},
                ],
            },
        )

        loader = PipelineLoader(tmp_path)
        pipeline = loader.load()

        assert pipeline is not None
        assert len(pipeline.steps) == 1

    def test_retorna_none_sem_pipeline_yaml(self, tmp_path):
        """Retorna None quando pipeline.yaml não existe (modo legado)."""
        loader = PipelineLoader(tmp_path)
        assert loader.load() is None

    def test_retorna_none_yaml_invalido(self, tmp_path):
        """Retorna None para YAML malformado."""
        (tmp_path / "pipeline.yaml").write_text("invalid: [yaml: {broken", encoding="utf-8")

        loader = PipelineLoader(tmp_path)
        assert loader.load() is None

    def test_retorna_none_yaml_nao_dict(self, tmp_path):
        """Retorna None quando YAML não é um dict."""
        (tmp_path / "pipeline.yaml").write_text("- item1\n- item2\n", encoding="utf-8")

        loader = PipelineLoader(tmp_path)
        assert loader.load() is None

    def test_parseia_step_file_com_frontmatter_e_quality_gate(self, tmp_path):
        """Parseia step file .md com quality gate — config vem do pipeline.yaml."""
        step_content = """\
---
model_tier: fast
on_reject: plan
max_review_cycles: 5
---
# Planejamento

Instruções detalhadas do step.

## Inputs

- Requisitos do cliente
- Contexto do produto

## Expected Outputs

- Documento de especificação
- Critérios de aceite

## Quality Gate

- Arquivo spec.md existe
- Contém pelo menos 3 critérios de aceite
- Especificação coerente com requisitos

## Veto Conditions

- Escopo indefinido
- Requisitos contraditórios
"""
        _write_step_file(tmp_path, "plan.md", step_content)
        _write_pipeline_yaml(
            tmp_path,
            {
                "name": "Test",
                "pipeline": {
                    "steps": [
                        {
                            "id": "plan",
                            "name": "Plan",
                            "agent": "po",
                            "file": "plan.md",
                            "model_tier": "fast",
                            "on_reject": "plan",
                            "max_review_cycles": 5,
                        },
                    ],
                },
            },
        )

        loader = PipelineLoader(tmp_path)
        pipeline = loader.load()
        step = pipeline.steps[0]

        # Configuração vem do pipeline.yaml (frontmatter é ignorado)
        assert step.model_tier == "fast"
        assert step.on_reject == "plan"
        assert step.max_review_cycles == 5

        # Seções parseadas
        assert len(step.inputs) == 2
        assert "Requisitos do cliente" in step.inputs
        assert len(step.expected_outputs) == 2
        assert "Documento de especificação" in step.expected_outputs

        # Quality gate com detecção de tipo
        assert len(step.quality_gate) == 3
        assert step.quality_gate[0].check_type == "file"  # "existe"
        assert step.quality_gate[1].check_type == "structural"  # "pelo menos"
        assert step.quality_gate[2].check_type == "semantic"  # padrão

        # Veto conditions
        assert len(step.veto_conditions) == 2
        assert "Escopo indefinido" in step.veto_conditions

    def test_parseia_step_file_sem_frontmatter(self, tmp_path):
        """Parseia step file sem frontmatter (apenas corpo)."""
        step_content = """\
# Desenvolvimento

Instruções sem frontmatter.

## Inputs

- Especificação aprovada
"""
        _write_step_file(tmp_path, "dev.md", step_content)
        _write_pipeline_yaml(
            tmp_path,
            {
                "name": "Test",
                "pipeline": {
                    "steps": [
                        {
                            "id": "dev",
                            "name": "Dev",
                            "agent": "dev-backend",
                            "file": "dev.md",
                            "model_tier": "powerful",
                        },
                    ],
                },
            },
        )

        loader = PipelineLoader(tmp_path)
        pipeline = loader.load()
        step = pipeline.steps[0]

        assert step.model_tier == "powerful"
        assert len(step.inputs) == 1
        assert "Especificação aprovada" in step.inputs
        assert step.instructions != ""

    def test_quality_gate_tipo_file(self, tmp_path):
        """Detecta tipo 'file' para checks com palavras-chave de arquivo."""
        body = "## Quality Gate\n\n- Arquivo README.md existe\n- Bytes do artefato > 0\n"
        checks = PipelineLoader._parse_quality_gate(body)

        assert len(checks) == 2
        assert all(c.check_type == "file" for c in checks)

    def test_quality_gate_tipo_structural(self, tmp_path):
        """Detecta tipo 'structural' para checks com palavras-chave estruturais."""
        body = "## Quality Gate\n\n- Contém pelo menos 5 itens\n- Formato JSON válido\n"
        checks = PipelineLoader._parse_quality_gate(body)

        assert len(checks) == 2
        assert all(c.check_type == "structural" for c in checks)

    def test_quality_gate_tipo_semantic(self):
        """Detecta tipo 'semantic' como padrão para checks genéricos."""
        body = "## Quality Gate\n\n- Código segue boas práticas\n- Lógica coerente\n"
        checks = PipelineLoader._parse_quality_gate(body)

        assert len(checks) == 2
        assert all(c.check_type == "semantic" for c in checks)

    def test_parse_list_section_com_checkbox(self):
        """Parseia itens de lista com checkbox markdown."""
        body = "## Inputs\n\n- [x] Item completo\n- [ ] Item pendente\n"
        items = PipelineLoader._parse_list_section(body, "Inputs")

        assert len(items) == 2
        assert "Item completo" in items
        assert "Item pendente" in items

    def test_parse_list_section_inexistente(self):
        """Retorna lista vazia para seção inexistente."""
        body = "## Outra Seção\n\n- Item qualquer\n"
        items = PipelineLoader._parse_list_section(body, "Inputs")
        assert items == []

    def test_frontmatter_ignorado_config_vem_do_pipeline_yaml(self, tmp_path):
        """Frontmatter é ignorado — configuração vem exclusivamente do pipeline.yaml."""
        step_content = """\
---
on_reject: do-frontmatter
model_tier: fast
---
# Step
Instruções.
"""
        _write_step_file(tmp_path, "review.md", step_content)
        _write_pipeline_yaml(
            tmp_path,
            {
                "name": "Test",
                "pipeline": {
                    "steps": [
                        {
                            "id": "review",
                            "name": "Review",
                            "agent": "code-review",
                            "file": "review.md",
                            "on_reject": "dev",
                            "model_tier": "powerful",
                        },
                    ],
                },
            },
        )

        loader = PipelineLoader(tmp_path)
        pipeline = loader.load()
        step = pipeline.steps[0]

        # Toda configuração vem do pipeline.yaml, frontmatter ignorado
        assert step.on_reject == "dev"
        assert step.model_tier == "powerful"

    def test_step_file_nao_encontrado(self, tmp_path):
        """Step file inexistente é tratado graciosamente."""
        _write_pipeline_yaml(
            tmp_path,
            {
                "name": "Test",
                "pipeline": {
                    "steps": [
                        {
                            "id": "s1",
                            "name": "Step 1",
                            "agent": "po",
                            "file": "nao_existe.md",
                        },
                    ],
                },
            },
        )

        loader = PipelineLoader(tmp_path)
        pipeline = loader.load()

        assert pipeline is not None
        assert len(pipeline.steps) == 1
        # Instruções permanecem vazias
        assert pipeline.steps[0].instructions == ""

    def test_agents_como_string_vira_lista(self, tmp_path):
        """Campo 'agents' como string é convertido para lista."""
        _write_pipeline_yaml(
            tmp_path,
            {
                "name": "Test",
                "pipeline": {
                    "steps": [
                        {"id": "s1", "name": "Step", "agents": "dev-backend"},
                    ],
                },
            },
        )

        loader = PipelineLoader(tmp_path)
        pipeline = loader.load()

        assert pipeline.steps[0].agents == ["dev-backend"]

    def test_frontmatter_invalido_retorna_corpo_inteiro(self):
        """Frontmatter YAML inválido é ignorado; corpo inteiro é retornado."""
        content = "---\ninvalid: [yaml: {broken\n---\n# Body\nConteúdo."
        fm, body = PipelineLoader._parse_frontmatter(content)

        assert fm == {}
        assert "---" in body or "Body" in body  # retorna conteúdo original

    def test_frontmatter_nao_dict_retorna_corpo_inteiro(self):
        """Frontmatter que não é dict é ignorado."""
        content = "---\n- item1\n- item2\n---\n# Body"
        fm, body = PipelineLoader._parse_frontmatter(content)

        assert fm == {}

    def test_parse_frontmatter_sem_fechamento(self):
        """Frontmatter sem segundo '---' retorna conteúdo original."""
        content = "---\nkey: value\n# Sem fechamento"
        fm, body = PipelineLoader._parse_frontmatter(content)

        assert fm == {}
        assert body == content
