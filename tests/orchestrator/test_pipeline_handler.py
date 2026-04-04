"""Testes para o PipelineHandler extraído do engine."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_squad.orchestrator.pipeline_handler import PipelineHandler


@pytest.fixture
def mock_executor():
    """Cria mock do PipelineExecutor."""
    executor = MagicMock()
    return executor


@pytest.fixture
def mock_journal():
    """Cria mock do JournalStore."""
    journal = MagicMock()
    return journal


@pytest.fixture
def mock_graph():
    """Cria mock do GraphStore."""
    graph = MagicMock()
    graph.ingest = AsyncMock()
    return graph


@pytest.fixture
def handler(mock_executor, mock_journal, mock_graph):
    """Cria PipelineHandler com demand_id fixo."""
    return PipelineHandler(
        pipeline_executor=mock_executor,
        journal=mock_journal,
        graph=mock_graph,
        get_demand_id=lambda: "demanda-1",
    )


@pytest.fixture
def handler_no_pipeline(mock_journal, mock_graph):
    """Cria PipelineHandler sem pipeline configurado."""
    return PipelineHandler(
        pipeline_executor=None,
        journal=mock_journal,
        graph=mock_graph,
        get_demand_id=lambda: "demanda-1",
    )


@pytest.fixture
def handler_no_demand(mock_executor, mock_journal, mock_graph):
    """Cria PipelineHandler sem demanda ativa."""
    return PipelineHandler(
        pipeline_executor=mock_executor,
        journal=mock_journal,
        graph=mock_graph,
        get_demand_id=lambda: "",
    )


# --- handle_get_pipeline_state ---


@pytest.mark.asyncio
async def test_get_pipeline_state_retorna_estado(handler, mock_executor) -> None:
    """Deve retornar estado formatado do pipeline."""
    mock_executor.format_state_for_prompt.return_value = "Step 1: PO (em andamento)"
    result = await handler.handle_get_pipeline_state()
    assert result == "Step 1: PO (em andamento)"
    mock_executor.format_state_for_prompt.assert_called_once_with("demanda-1")


@pytest.mark.asyncio
async def test_get_pipeline_state_sem_pipeline(handler_no_pipeline) -> None:
    """Deve retornar mensagem sobre modo legado se pipeline não configurado."""
    result = await handler_no_pipeline.handle_get_pipeline_state()
    assert "modo legado" in result.lower() or "nao configurado" in result.lower()


@pytest.mark.asyncio
async def test_get_pipeline_state_sem_demanda(handler_no_demand) -> None:
    """Deve retornar mensagem sobre nenhuma demanda ativa."""
    result = await handler_no_demand.handle_get_pipeline_state()
    assert "demanda" in result.lower()


# --- handle_advance_step ---


@pytest.mark.asyncio
async def test_advance_step_avanca_para_proximo(handler, mock_executor) -> None:
    """Deve avançar para o próximo step e retornar sua descrição."""
    current_step = MagicMock()
    current_step.id = "step-1"
    mock_executor.get_current_step.return_value = current_step

    next_step = MagicMock()
    next_step.name = "Dev Backend"
    next_step.id = "step-2"
    mock_executor.complete_step.return_value = next_step

    result = await handler.handle_advance_step()
    assert "Dev Backend" in result
    assert "step-2" in result


@pytest.mark.asyncio
async def test_advance_step_pipeline_concluido(
    handler, mock_executor, mock_journal, mock_graph
) -> None:
    """Quando pipeline conclui, deve alimentar grafo e retornar 'concluido'."""
    current_step = MagicMock()
    current_step.id = "step-final"
    mock_executor.get_current_step.return_value = current_step
    mock_executor.complete_step.return_value = None  # Pipeline concluído

    mock_journal.read.return_value = {
        "demand_text": "Criar feature X",
        "decisions": [
            {"description": "delegou para dev"},
            {"description": "aprovado QA"},
        ],
    }

    result = await handler.handle_advance_step()
    assert "concluido" in result.lower()
    mock_graph.ingest.assert_called_once()


@pytest.mark.asyncio
async def test_advance_step_sem_step_ativo(handler, mock_executor) -> None:
    """Sem step ativo, deve retornar mensagem informativa."""
    mock_executor.get_current_step.return_value = None
    result = await handler.handle_advance_step()
    assert "step ativo" in result.lower() or "avancar" in result.lower()


@pytest.mark.asyncio
async def test_advance_step_sem_pipeline(handler_no_pipeline) -> None:
    """Deve retornar mensagem se pipeline não configurado."""
    result = await handler_no_pipeline.handle_advance_step()
    assert "nao configurado" in result.lower()


@pytest.mark.asyncio
async def test_advance_step_sem_demanda(handler_no_demand) -> None:
    """Deve retornar mensagem se nenhuma demanda ativa."""
    result = await handler_no_demand.handle_advance_step()
    assert "demanda" in result.lower()


# --- handle_skip_step ---


@pytest.mark.asyncio
async def test_skip_step_com_proximo(handler, mock_executor) -> None:
    """Pular step com próximo disponível."""
    next_step = MagicMock()
    next_step.name = "QA"
    mock_executor.skip_step.return_value = next_step

    result = await handler.handle_skip_step("step-2")
    assert "pulado" in result.lower()
    assert "QA" in result


@pytest.mark.asyncio
async def test_skip_step_pipeline_concluido(handler, mock_executor) -> None:
    """Pular step quando é o último — pipeline concluído."""
    mock_executor.skip_step.return_value = None
    result = await handler.handle_skip_step("step-final")
    assert "concluido" in result.lower()


@pytest.mark.asyncio
async def test_skip_step_sem_pipeline(handler_no_pipeline) -> None:
    """Deve retornar mensagem se pipeline não configurado."""
    result = await handler_no_pipeline.handle_skip_step("any")
    assert "nao configurado" in result.lower()


# --- handle_rerun_step ---


@pytest.mark.asyncio
async def test_rerun_step_sucesso(handler, mock_executor) -> None:
    """Re-executar step existente."""
    mock_executor.rerun_step.return_value = True
    result = await handler.handle_rerun_step("step-1")
    assert "re-iniciado" in result.lower()


@pytest.mark.asyncio
async def test_rerun_step_nao_encontrado(handler, mock_executor) -> None:
    """Re-executar step inexistente."""
    mock_executor.rerun_step.return_value = False
    result = await handler.handle_rerun_step("step-404")
    assert "nao encontrado" in result.lower()


@pytest.mark.asyncio
async def test_rerun_step_sem_pipeline(handler_no_pipeline) -> None:
    """Deve retornar mensagem se pipeline não configurado."""
    result = await handler_no_pipeline.handle_rerun_step("any")
    assert "nao configurado" in result.lower()


@pytest.mark.asyncio
async def test_rerun_step_sem_demanda(handler_no_demand) -> None:
    """Deve retornar mensagem se nenhuma demanda ativa."""
    result = await handler_no_demand.handle_rerun_step("any")
    assert "demanda" in result.lower()
