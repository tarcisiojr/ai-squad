## ADDED Requirements

### Requirement: Execucao paralela de agentes
O engine SHALL suportar execucao de multiplos agentes simultaneamente.

#### Scenario: Dois agentes em paralelo
- **WHEN** invoke_parallel e chamado com 2 agentes
- **THEN** o engine MUST executar ambos via asyncio.gather, cada um com sua propria conversa no Telegram

#### Scenario: Conversas independentes
- **WHEN** multiplos agentes estao executando em paralelo
- **THEN** cada agente MUST ter seu proprio historico de conversa independente

#### Scenario: Resultado consolidado
- **WHEN** todos os agentes paralelos concluem
- **THEN** o engine MUST retornar todos os resultados ao Squad Lead como lista
