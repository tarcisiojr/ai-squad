## ADDED Requirements

### Requirement: Feedback periodico durante execucao
O engine SHALL enviar feedback ao usuario via Telegram durante execucoes longas.

#### Scenario: Feedback a cada 30 segundos
- **WHEN** um agente esta executando ha mais de 30 segundos
- **THEN** o engine MUST enviar mensagem curta no Telegram informando qual agente esta trabalhando e ha quanto tempo

#### Scenario: Formato do feedback
- **WHEN** o engine envia feedback
- **THEN** a mensagem MUST seguir o formato: "[<agente>] Trabalhando... (<tempo>)"

#### Scenario: Feedback nao repete
- **WHEN** o feedback ja foi enviado
- **THEN** a proxima mensagem MUST atualizar o tempo, nao repetir a mesma mensagem
