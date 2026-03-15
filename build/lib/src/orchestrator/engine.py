"""Motor de orquestração com máquina de estados."""

from typing import Callable

from src.models import DemandState, VALID_TRANSITIONS, AgentStatus
from src.adapters.interface import AIAgentAdapter
from src.barramento.interface import MessageBus
from src.orchestrator.state import StateManager


class InvalidTransitionError(Exception):
    """Erro para transições de estado inválidas."""

    pass


class OrchestrationEngine:
    """Motor de orquestração que controla o ciclo de vida de demandas.

    Usa máquina de estados para garantir transições válidas,
    despacha agentes via adapter injetado, e roteia decisões
    humanas ao barramento de mensageria.
    """

    def __init__(
        self,
        adapter: AIAgentAdapter,
        message_bus: MessageBus,
        state_manager: StateManager,
    ) -> None:
        self._adapter = adapter
        self._message_bus = message_bus
        self._state_manager = state_manager

        # Registra callback para intervenção humana
        self._adapter.on_human_needed(self._handle_human_needed)

    def transition(self, demand_id: str, new_state: DemandState) -> None:
        """Realiza transição de estado para uma demanda."""
        current = self._state_manager.get_state(demand_id)

        if new_state not in VALID_TRANSITIONS.get(current, []):
            raise InvalidTransitionError(
                f"Transição inválida: {current.value} → {new_state.value}. "
                f"Transições válidas: {[s.value for s in VALID_TRANSITIONS.get(current, [])]}"
            )

        self._state_manager.set_state(demand_id, new_state)

    def get_state(self, demand_id: str) -> DemandState:
        """Retorna o estado atual de uma demanda."""
        return self._state_manager.get_state(demand_id)

    async def dispatch_agent(
        self, demand_id: str, agent_name: str, prompt: str, context: dict
    ) -> str:
        """Despacha agente para execução via adapter."""
        context["demand_id"] = demand_id
        context["agent_name"] = agent_name

        resultado = await self._adapter.run(prompt, context)
        return resultado

    async def _handle_human_needed(self, question: str) -> str:
        """Roteia pedido de decisão humana ao barramento."""
        resposta = await self._message_bus.send_approval_request(
            user_id="default",
            question=question,
            options=["Aprovar", "Rejeitar"],
        )
        return resposta

    async def request_approval(
        self,
        demand_id: str,
        user_id: str,
        question: str,
        options: list[str],
    ) -> str:
        """Solicita aprovação humana via barramento."""
        resposta = await self._message_bus.send_approval_request(
            user_id=user_id,
            question=question,
            options=options,
        )
        return resposta

    async def notify_user(self, user_id: str, message: str) -> None:
        """Envia notificação ao usuário via barramento."""
        await self._message_bus.notify(user_id, message)

    async def _agent_conversation(
        self, demand_id: str, user_id: str, agent_name: str,
        initial_prompt: str, context: dict,
    ) -> str:
        """Conduz conversa iterativa entre agente e usuário.

        O agente responde e o usuário pode continuar conversando.
        Quando o agente produz um resultado final, o usuário aprova ou rejeita.
        Retorna o resultado final aprovado, ou string vazia se rejeitado/cancelado.
        """
        historico = initial_prompt
        agent_label = context.get("agent_label", agent_name)

        while True:
            resposta_agente = await self.dispatch_agent(
                demand_id, agent_name, historico, context,
            )

            # Apresenta a resposta com opções: Aprovar, Rejeitar, ou responder
            aprovacao = await self.request_approval(
                demand_id, user_id,
                f"*[{agent_label}]*\n\n{resposta_agente}",
                ["✅ Aprovar", "❌ Cancelar", "💬 Responder"],
            )

            if aprovacao == "✅ Aprovar":
                return resposta_agente

            if aprovacao == "❌ Cancelar":
                return ""

            # Usuário quer responder — pede texto livre
            feedback = await self._message_bus.ask_user(
                user_id,
                f"*[{agent_label}]* Escreva sua resposta:",
            )

            # Adiciona feedback ao histórico para próxima iteração
            historico = (
                f"{historico}\n\n"
                f"--- Resposta anterior do agente ---\n{resposta_agente}\n\n"
                f"--- Feedback do usuário ---\n{feedback}"
            )

    async def run_demand_cycle(
        self, demand_id: str, user_id: str, demand_text: str
    ) -> None:
        """Executa o ciclo completo de uma demanda.

        idle → po_working → awaiting_plan_approval → dev_working
        → awaiting_pr_approval → ci_running → qa_validating → done
        """
        # PO trabalha na especificação com conversa iterativa
        self.transition(demand_id, DemandState.PO_WORKING)
        await self.notify_user(user_id, "📋 PO iniciando especificação...")

        plano = await self._agent_conversation(
            demand_id, user_id, "po", demand_text,
            {"fase": "especificacao", "agent_label": "📋 PO"},
        )

        if not plano:
            await self.notify_user(user_id, f"Demanda {demand_id} cancelada.")
            return

        # Dev trabalha na implementação
        self.transition(demand_id, DemandState.AWAITING_PLAN_APPROVAL)
        self.transition(demand_id, DemandState.DEV_WORKING)
        await self.notify_user(user_id, "🔧 Dev iniciando implementação...")

        resultado_dev = await self._agent_conversation(
            demand_id, user_id, "dev-orchestrator", plano,
            {"fase": "implementacao", "agent_label": "🔧 Dev"},
        )

        if not resultado_dev:
            await self.notify_user(user_id, f"Demanda {demand_id} cancelada na fase de desenvolvimento.")
            return

        # Aguarda aprovação do PR
        self.transition(demand_id, DemandState.AWAITING_PR_APPROVAL)
        aprovacao_pr = await self.request_approval(
            demand_id, user_id,
            f"*[🔧 Dev]* PR pronto para revisão:\n\n{resultado_dev}",
            ["✅ Aprovar PR", "❌ Rejeitar PR"],
        )

        if aprovacao_pr != "✅ Aprovar PR":
            await self.notify_user(user_id, f"PR rejeitado. Demanda {demand_id} encerrada.")
            return

        # CI executa
        self.transition(demand_id, DemandState.CI_RUNNING)
        await self.notify_user(user_id, "⚙️ CI executando...")

        # QA valida
        self.transition(demand_id, DemandState.QA_VALIDATING)
        await self.notify_user(user_id, "🧪 QA validando...")

        await self.dispatch_agent(
            demand_id, "qa", resultado_dev, {"fase": "validacao", "agent_label": "🧪 QA"}
        )

        # Conclusão
        self.transition(demand_id, DemandState.DONE)
        await self.notify_user(user_id, "✅ Demanda concluída!")
