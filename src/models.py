"""Modelos e enums compartilhados da plataforma."""

from enum import Enum


class AgentStatus(Enum):
    """Status possíveis de um agente IA."""

    IDLE = "idle"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    ERROR = "error"
    DONE = "done"


class DemandState(Enum):
    """Estados do ciclo de vida de uma demanda.

    Transições válidas:
        idle → po_working
        po_working → awaiting_plan_approval
        awaiting_plan_approval → dev_working
        dev_working → awaiting_pr_approval
        awaiting_pr_approval → ci_running
        ci_running → qa_validating
        qa_validating → done
    """

    IDLE = "idle"
    PO_WORKING = "po_working"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    DEV_WORKING = "dev_working"
    AWAITING_PR_APPROVAL = "awaiting_pr_approval"
    CI_RUNNING = "ci_running"
    QA_VALIDATING = "qa_validating"
    DONE = "done"


# Mapeamento de transições válidas
VALID_TRANSITIONS: dict[DemandState, list[DemandState]] = {
    DemandState.IDLE: [DemandState.PO_WORKING],
    DemandState.PO_WORKING: [DemandState.AWAITING_PLAN_APPROVAL],
    DemandState.AWAITING_PLAN_APPROVAL: [DemandState.DEV_WORKING],
    DemandState.DEV_WORKING: [DemandState.AWAITING_PR_APPROVAL],
    DemandState.AWAITING_PR_APPROVAL: [DemandState.CI_RUNNING],
    DemandState.CI_RUNNING: [DemandState.QA_VALIDATING],
    DemandState.QA_VALIDATING: [DemandState.DONE],
    DemandState.DONE: [],
}
