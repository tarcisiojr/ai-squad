## MODIFIED Requirements

### Requirement: Despacho de agentes via adapter
O orquestrador SHALL passar contexto completo ao Squad Lead quando um agente conclui, incluindo resultado, verificacao, e estado dos artefatos. O orquestrador SHALL eliminar estado compartilhado entre tasks concorrentes.

#### Scenario: Squad Lead recebe contexto completo apos agente concluir
- **WHEN** um agente background conclui e o Squad Lead e disparado
- **THEN** o Squad Lead MUST receber: resultado do agente, resultado da verificacao (passed/failed + detalhes), e estado dos agentes

#### Scenario: Atividades paralelas nao corrompem estado
- **WHEN** dois agentes estao rodando em background simultaneamente
- **THEN** cada agente MUST ter seu proprio user_id e demand_id sem compartilhar estado de instancia
