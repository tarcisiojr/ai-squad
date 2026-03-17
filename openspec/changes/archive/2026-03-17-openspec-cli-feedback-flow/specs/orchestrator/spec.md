## MODIFIED Requirements

### Requirement: Engine com feedback durante dispatch
O engine SHALL enviar feedback periodico ao Telegram enquanto um agente esta sendo executado.

#### Scenario: Feedback em background
- **WHEN** dispatch_agent e chamado
- **THEN** o engine MUST iniciar task em background que envia feedback a cada 30 segundos ate o agente concluir
