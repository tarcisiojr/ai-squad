# Spec: State Awareness

## Objetivo
Squad Lead deve ter consciência completa do estado de todas as demandas ativas ANTES de tomar qualquer decisão.

## Nova Tool: `get_demand_state()`

### Assinatura
```python
get_demand_state(demand_id: str | None = None) -> dict
```

### Comportamento
- Se `demand_id` fornecido: retorna estado daquela demanda
- Se `demand_id` é None: retorna TODAS as demandas ativas (não-idle, não-done)

### Retorno
```json
{
  "active_demands": [
    {
      "demand_id": "abc-123",
      "state": "awaiting_plan_approval",
      "state_description": "Esperando aprovação do plano pelo usuário",
      "last_agent": "po",
      "last_agent_status": "done",
      "running_agents": [],
      "stalled": false,
      "stalled_since": null,
      "next_expected_action": "Usuário aprovar ou rejeitar o plano",
      "artifacts": {"proposal": true, "specs": true, "design": true, "tasks": true}
    }
  ],
  "summary": "1 demanda ativa: abc-123 aguardando aprovação do plano"
}
```

### Campo `stalled`
Uma demanda é considerada "parada" se:
- Estado não é `idle` nem `done`
- Nenhum agente está rodando para ela
- Último agente terminou há mais de 5 minutos
- Nenhuma ação do usuário foi recebida

### Campo `next_expected_action`
Mapeamento estado → próxima ação esperada:

| Estado | Próxima ação |
|--------|-------------|
| `po_working` | Aguardar PO concluir |
| `awaiting_plan_approval` | Usuário aprovar/rejeitar plano |
| `dev_working` | Aguardar Dev concluir |
| `awaiting_pr_approval` | Usuário aprovar/rejeitar PR |
| `ci_running` | Aguardar CI passar |
| `qa_validating` | Aguardar QA concluir |

## Integração com Squad Lead

### No AGENTS.md
```
ANTES de agir em qualquer mensagem:
1. Chame get_demand_state() para saber o estado atual
2. Se há demandas ativas, considere se a mensagem se refere a elas
3. Se há demandas paradas, RETOME antes de criar novas
```

### No Engine
- Tool registrada como MCP callback no `run_squad_lead()`
- Lê de `StateManager.get_all_demands()` + `RunningAgent` status
- Calcula campo `stalled` baseado em timestamps

## Critérios de Aceite

- [ ] `get_demand_state()` sem argumentos retorna todas demandas ativas
- [ ] `get_demand_state("id")` retorna estado específico
- [ ] Campo `stalled` é true quando demanda parou há mais de 5 minutos
- [ ] Campo `next_expected_action` é correto para cada estado
- [ ] Campo `artifacts` reflete existência real dos artefatos openspec
- [ ] Squad Lead consulta estado ANTES de decidir ação
