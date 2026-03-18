"""Testes para pipeline_state: StepState, PipelineState e PipelineExecutor.

Cobre serialização, gerenciamento de estado, avanço de steps,
loops de rejeição, persistência e formatação visual.
"""

from pathlib import Path

import pytest

from src.orchestrator.pipeline import PipelineConfig, StepConfig
from src.orchestrator.pipeline_state import PipelineExecutor, PipelineState, StepState

# --- Fixtures ---


def _criar_pipeline_config() -> PipelineConfig:
    """Cria PipelineConfig de teste com 4 steps, incluindo checkpoint e on_reject."""
    return PipelineConfig(
        name="pipeline-teste",
        description="Pipeline para testes unitários",
        steps=[
            StepConfig(
                id="spec",
                name="Especificação",
                agent="po",
                step_type="agent",
            ),
            StepConfig(
                id="dev",
                name="Desenvolvimento",
                agents=["dev-backend", "dev-frontend"],
                step_type="agent",
            ),
            StepConfig(
                id="review",
                name="Code Review",
                agent="code-review",
                step_type="checkpoint",
                on_reject="dev",
                max_review_cycles=2,
            ),
            StepConfig(
                id="qa",
                name="QA",
                agent="qa",
                step_type="agent",
            ),
        ],
    )


@pytest.fixture
def pipeline_config() -> PipelineConfig:
    """Fixture com PipelineConfig de 4 steps."""
    return _criar_pipeline_config()


@pytest.fixture
def executor(tmp_path: Path, pipeline_config: PipelineConfig) -> PipelineExecutor:
    """Fixture com PipelineExecutor usando diretório temporário."""
    return PipelineExecutor(state_dir=str(tmp_path), pipeline=pipeline_config)


# --- TestStepState ---


class TestStepState:
    """Testes para serialização e valores padrão do StepState."""

    def test_valores_padrao(self) -> None:
        """Verifica que StepState tem valores padrão corretos."""
        step = StepState(step_id="s1", name="Step 1")

        assert step.status == "pending"
        assert step.agents == []
        assert step.agent_status == {}
        assert step.started_at == ""
        assert step.completed_at == ""
        assert step.quality_gate_result == ""
        assert step.review_cycle == 0
        assert step.review_history == []
        assert step.retries == 0
        assert step.error == ""

    def test_to_dict_e_from_dict_roundtrip(self) -> None:
        """Verifica serialização e deserialização ida-e-volta."""
        original = StepState(
            step_id="dev",
            name="Desenvolvimento",
            status="running",
            agents=["dev-backend", "dev-frontend"],
            agent_status={"dev-backend": "working", "dev-frontend": "idle"},
            started_at="2026-03-16T10:00:00+00:00",
            completed_at="",
            quality_gate_result="passed",
            review_cycle=1,
            review_history=[{"cycle": 1, "result": "rejected", "feedback": "faltou teste"}],
            retries=2,
            error="timeout anterior",
        )

        dados = original.to_dict()
        restaurado = StepState.from_dict(dados)

        assert restaurado.step_id == original.step_id
        assert restaurado.name == original.name
        assert restaurado.status == original.status
        assert restaurado.agents == original.agents
        assert restaurado.agent_status == original.agent_status
        assert restaurado.started_at == original.started_at
        assert restaurado.completed_at == original.completed_at
        assert restaurado.quality_gate_result == original.quality_gate_result
        assert restaurado.review_cycle == original.review_cycle
        assert restaurado.review_history == original.review_history
        assert restaurado.retries == original.retries
        assert restaurado.error == original.error

    def test_from_dict_com_dados_parciais(self) -> None:
        """Verifica que from_dict preenche valores padrão para campos ausentes."""
        dados = {"step_id": "x", "name": "X"}
        step = StepState.from_dict(dados)

        assert step.step_id == "x"
        assert step.status == "pending"
        assert step.review_cycle == 0


# --- TestPipelineState ---


class TestPipelineState:
    """Testes para serialização e acesso ao PipelineState."""

    def test_to_dict_e_from_dict_roundtrip(self) -> None:
        """Verifica serialização completa incluindo steps aninhados."""
        state = PipelineState(
            demand_id="D-001",
            pipeline_name="pipeline-teste",
            status="running",
            current_step="dev",
            started_at="2026-03-16T10:00:00+00:00",
            updated_at="2026-03-16T10:05:00+00:00",
            steps={
                "spec": StepState(step_id="spec", name="Spec", status="completed"),
                "dev": StepState(step_id="dev", name="Dev", status="running"),
            },
        )

        dados = state.to_dict()
        restaurado = PipelineState.from_dict(dados)

        assert restaurado.demand_id == "D-001"
        assert restaurado.pipeline_name == "pipeline-teste"
        assert restaurado.status == "running"
        assert restaurado.current_step == "dev"
        assert len(restaurado.steps) == 2
        assert restaurado.steps["spec"].status == "completed"
        assert restaurado.steps["dev"].status == "running"

    def test_get_step_state_existente(self) -> None:
        """Verifica que get_step_state retorna step existente."""
        state = PipelineState(
            demand_id="D-001",
            steps={"spec": StepState(step_id="spec", name="Spec", status="completed")},
        )

        resultado = state.get_step_state("spec")
        assert resultado is not None
        assert resultado.status == "completed"

    def test_get_step_state_inexistente(self) -> None:
        """Verifica que get_step_state retorna None para step inexistente."""
        state = PipelineState(demand_id="D-001")
        assert state.get_step_state("nao-existe") is None


# --- TestPipelineExecutor ---


class TestPipelineExecutor:
    """Testes para o PipelineExecutor: ciclo de vida completo do pipeline."""

    def test_start_pipeline_cria_estado_para_todos_os_steps(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que start_pipeline inicializa todos os steps com primeiro running."""
        state = executor.start_pipeline("D-001")

        assert state.demand_id == "D-001"
        assert state.pipeline_name == "pipeline-teste"
        assert state.status == "running"
        assert state.current_step == "spec"
        assert len(state.steps) == 4

        # Primeiro step deve estar running
        assert state.steps["spec"].status == "running"
        assert state.steps["spec"].started_at != ""

        # Demais devem estar pending
        assert state.steps["dev"].status == "pending"
        assert state.steps["review"].status == "pending"
        assert state.steps["qa"].status == "pending"

    def test_complete_step_avanca_para_proximo(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que completar um step avança para o próximo."""
        executor.start_pipeline("D-001")

        proximo = executor.complete_step("D-001", "spec", quality_gate_result="passed")

        assert proximo is not None
        assert proximo.id == "dev"

        state = executor.load_state("D-001")
        assert state is not None
        assert state.current_step == "dev"
        assert state.steps["spec"].status == "completed"
        assert state.steps["dev"].status == "running"

    def test_complete_step_com_quality_gate_falho_nao_avanca(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que quality gate failed não avança o pipeline."""
        executor.start_pipeline("D-001")

        proximo = executor.complete_step("D-001", "spec", quality_gate_result="failed")

        assert proximo is None

        state = executor.load_state("D-001")
        assert state is not None
        assert state.current_step == "spec"
        assert state.steps["spec"].status == "failed"
        assert state.steps["spec"].retries == 1

    def test_pipeline_completa_quando_ultimo_step_finaliza(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que pipeline muda para completed ao finalizar último step."""
        executor.start_pipeline("D-001")

        # Avança spec → dev → review → qa → conclusão
        executor.complete_step("D-001", "spec")
        executor.complete_step("D-001", "dev")
        executor.complete_step("D-001", "review")
        resultado = executor.complete_step("D-001", "qa")

        assert resultado is None

        state = executor.load_state("D-001")
        assert state is not None
        assert state.status == "completed"
        assert state.current_step == ""

    def test_skip_step_marca_como_skipped_e_avanca(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que skip_step pula o step e avança para o próximo."""
        executor.start_pipeline("D-001")

        proximo = executor.skip_step("D-001", "spec")

        assert proximo is not None
        assert proximo.id == "dev"

        state = executor.load_state("D-001")
        assert state is not None
        assert state.steps["spec"].status == "skipped"
        assert state.steps["spec"].completed_at != ""

    def test_rerun_step_reseta_para_running(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que rerun_step reseta o step para running."""
        executor.start_pipeline("D-001")
        executor.complete_step("D-001", "spec")

        resultado = executor.rerun_step("D-001", "spec")

        assert resultado is True

        state = executor.load_state("D-001")
        assert state is not None
        assert state.current_step == "spec"
        assert state.steps["spec"].status == "running"
        assert state.steps["spec"].quality_gate_result == ""
        assert state.steps["spec"].error == ""
        assert state.status == "running"

    def test_handle_reject_volta_para_step_on_reject(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que rejeição no review volta para o step dev."""
        executor.start_pipeline("D-001")
        executor.complete_step("D-001", "spec")
        executor.complete_step("D-001", "dev")

        # Review está em checkpoint; tratamos rejeição
        destino = executor.handle_reject("D-001", "review", "faltou tratamento de erro")

        assert destino == "dev"

        state = executor.load_state("D-001")
        assert state is not None
        assert state.current_step == "dev"
        assert state.steps["dev"].status == "running"
        assert state.steps["review"].status == "pending"

    def test_handle_reject_retorna_none_quando_max_review_cycles_atingido(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que handle_reject retorna None ao atingir max_review_cycles."""
        executor.start_pipeline("D-001")
        executor.complete_step("D-001", "spec")
        executor.complete_step("D-001", "dev")

        # max_review_cycles=2: ciclo 1 ok, ciclo 2 atinge limite
        resultado1 = executor.handle_reject("D-001", "review", "feedback 1")
        assert resultado1 == "dev"

        # Re-executa dev e volta ao review
        executor.complete_step("D-001", "dev")

        resultado2 = executor.handle_reject("D-001", "review", "feedback 2")
        assert resultado2 is None

        state = executor.load_state("D-001")
        assert state is not None
        assert state.status == "paused"
        assert state.steps["review"].status == "failed"

    def test_handle_reject_registra_review_history(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que handle_reject registra histórico de revisão."""
        executor.start_pipeline("D-001")
        executor.complete_step("D-001", "spec")
        executor.complete_step("D-001", "dev")

        executor.handle_reject("D-001", "review", "falta cobertura de testes")

        state = executor.load_state("D-001")
        assert state is not None

        historico = state.steps["review"].review_history
        assert len(historico) == 1
        assert historico[0]["cycle"] == 1
        assert historico[0]["result"] == "rejected"
        assert historico[0]["feedback"] == "falta cobertura de testes"
        assert "timestamp" in historico[0]

    def test_update_agent_status_atualiza_agente_individual(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que update_agent_status atualiza status de agente específico."""
        executor.start_pipeline("D-001")
        executor.complete_step("D-001", "spec")

        executor.update_agent_status("D-001", "dev", "dev-backend", "working")
        executor.update_agent_status("D-001", "dev", "dev-frontend", "idle")

        state = executor.load_state("D-001")
        assert state is not None
        assert state.steps["dev"].agent_status["dev-backend"] == "working"
        assert state.steps["dev"].agent_status["dev-frontend"] == "idle"

    def test_format_state_for_prompt_gera_saida_visual(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que format_state_for_prompt gera texto com ícones e informações."""
        executor.start_pipeline("D-001")
        executor.complete_step("D-001", "spec")

        saida = executor.format_state_for_prompt("D-001")

        # Verifica que contém elementos esperados
        assert "pipeline-teste" in saida
        assert "D-001" in saida
        assert "✅" in saida  # spec completado
        assert "🔄" in saida  # dev em execução
        assert "⏳" in saida  # steps pendentes
        assert "Desenvolvimento" in saida
        assert "checkpoint" in saida.lower()

    def test_format_state_for_prompt_demanda_inexistente(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que format_state_for_prompt retorna string vazia para demanda inexistente."""
        assert executor.format_state_for_prompt("nao-existe") == ""

    def test_load_state_persistencia_em_arquivo(
        self, executor: PipelineExecutor, tmp_path: Path,
    ) -> None:
        """Verifica que estado é persistido em JSON e pode ser recarregado."""
        executor.start_pipeline("D-001")
        executor.complete_step("D-001", "spec")

        # Cria novo executor para forçar leitura do disco
        novo_executor = PipelineExecutor(
            state_dir=str(tmp_path),
            pipeline=_criar_pipeline_config(),
        )

        state = novo_executor.load_state("D-001")
        assert state is not None
        assert state.demand_id == "D-001"
        assert state.current_step == "dev"
        assert state.steps["spec"].status == "completed"

    def test_load_state_retorna_none_para_demanda_inexistente(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que load_state retorna None quando não há estado salvo."""
        assert executor.load_state("nao-existe") is None

    def test_get_active_demands_retorna_pipelines_em_execucao(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que get_active_demands retorna apenas pipelines running/paused."""
        executor.start_pipeline("D-001")
        executor.start_pipeline("D-002")

        # Completa D-002 inteiramente
        executor.complete_step("D-002", "spec")
        executor.complete_step("D-002", "dev")
        executor.complete_step("D-002", "review")
        executor.complete_step("D-002", "qa")

        ativos = executor.get_active_demands()

        ids_ativos = [s.demand_id for s in ativos]
        assert "D-001" in ids_ativos
        assert "D-002" not in ids_ativos

    def test_get_current_step_retorna_step_config_correto(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que get_current_step retorna StepConfig do step atual."""
        executor.start_pipeline("D-001")

        step = executor.get_current_step("D-001")
        assert step is not None
        assert step.id == "spec"
        assert step.name == "Especificação"

        # Avança e verifica de novo
        executor.complete_step("D-001", "spec")
        step = executor.get_current_step("D-001")
        assert step is not None
        assert step.id == "dev"

    def test_get_current_step_retorna_none_para_demanda_inexistente(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que get_current_step retorna None sem estado."""
        assert executor.get_current_step("nao-existe") is None

    def test_checkpoint_step_recebe_status_checkpoint(
        self, executor: PipelineExecutor,
    ) -> None:
        """Verifica que step checkpoint recebe status 'checkpoint' ao ser ativado."""
        executor.start_pipeline("D-001")
        executor.complete_step("D-001", "spec")
        executor.complete_step("D-001", "dev")

        state = executor.load_state("D-001")
        assert state is not None
        assert state.current_step == "review"
        assert state.steps["review"].status == "checkpoint"
