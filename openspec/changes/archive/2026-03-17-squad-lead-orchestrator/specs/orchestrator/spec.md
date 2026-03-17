## MODIFIED Requirements

### Requirement: Engine como runtime
O OrchestrationEngine SHALL funcionar como runtime de execucao, sem fluxo fixo de demandas.

#### Scenario: Demanda processada pelo Squad Lead
- **WHEN** uma nova demanda e recebida
- **THEN** o engine MUST iniciar o Squad Lead com tools e deixar ele decidir o fluxo

#### Scenario: run_demand_cycle substituido
- **WHEN** o engine processa uma demanda
- **THEN** MUST usar run_squad_lead em vez de run_demand_cycle com sequencia fixa

## ADDED Requirements

### Requirement: Registro de tools para o Squad Lead
O engine SHALL registrar tools (invoke_agent, invoke_parallel, get_status, check_workspace) que o Squad Lead pode chamar durante execucao.

#### Scenario: Tools disponiveis no prompt
- **WHEN** o Squad Lead e iniciado
- **THEN** as tools MUST estar disponiveis para uso via Claude Agent SDK tool_use
