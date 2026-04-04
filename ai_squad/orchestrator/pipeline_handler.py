"""Handler para operações de pipeline — extraído do engine."""

import logging
from collections.abc import Callable

from ai_squad.orchestrator.graph import GraphStore
from ai_squad.orchestrator.journal import JournalStore
from ai_squad.orchestrator.pipeline_state import PipelineExecutor

logger = logging.getLogger("ai-squad.pipeline-handler")


class PipelineHandler:
    """Encapsula lógica de manipulação do pipeline declarativo.

    Recebe dependências explícitas em vez de acessar o engine diretamente.
    O engine registra os métodos como callbacks nos eventos correspondentes.
    """

    def __init__(
        self,
        pipeline_executor: PipelineExecutor | None,
        journal: JournalStore,
        graph: GraphStore,
        get_demand_id: Callable[[], str],
    ) -> None:
        self._executor = pipeline_executor
        self._journal = journal
        self._graph = graph
        self._get_demand_id = get_demand_id

    async def handle_get_pipeline_state(self) -> str:
        """Retorna estado atual do pipeline para a demanda ativa."""
        if not self._executor:
            return "Pipeline nao configurado. Operando em modo legado."
        demand_id = self._get_demand_id()
        if not demand_id:
            return "Nenhuma demanda ativa."
        return self._executor.format_state_for_prompt(demand_id)

    async def handle_advance_step(self) -> str:
        """Avança para o próximo step do pipeline."""
        if not self._executor:
            return "Pipeline nao configurado."
        demand_id = self._get_demand_id()
        if not demand_id:
            return "Nenhuma demanda ativa."
        current = self._executor.get_current_step(demand_id)
        if not current:
            return "Nenhum step ativo para avancar."
        next_step = self._executor.complete_step(demand_id, current.id)
        if next_step:
            return f"Avancado para step: {next_step.name} ({next_step.id})"

        # Pipeline concluído — alimenta grafo com resumo do journal
        journal_data = self._journal.read(demand_id)
        if journal_data:
            demand_text = journal_data.get("demand_text", "")
            decisions = journal_data.get("decisions", [])
            decisions_text = "; ".join(d.get("description", "") for d in decisions[-5:])
            await self._graph.ingest(
                f"Demanda {demand_id} concluida: {demand_text}. Decisoes: {decisions_text}",
                demand_id,
            )
        return "Pipeline concluido."

    async def handle_skip_step(self, step_id: str) -> str:
        """Pula um step específico do pipeline."""
        if not self._executor:
            return "Pipeline nao configurado."
        demand_id = self._get_demand_id()
        if not demand_id:
            return "Nenhuma demanda ativa."
        next_step = self._executor.skip_step(demand_id, step_id)
        if next_step:
            return f"Step '{step_id}' pulado. Proximo: {next_step.name}"
        return f"Step '{step_id}' pulado. Pipeline concluido."

    async def handle_rerun_step(self, step_id: str) -> str:
        """Re-executa um step específico do pipeline."""
        if not self._executor:
            return "Pipeline nao configurado."
        demand_id = self._get_demand_id()
        if not demand_id:
            return "Nenhuma demanda ativa."
        ok = self._executor.rerun_step(demand_id, step_id)
        if ok:
            return f"Step '{step_id}' re-iniciado."
        return f"Step '{step_id}' nao encontrado."
