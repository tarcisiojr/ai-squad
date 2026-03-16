## ADDED Requirements

### Requirement: Squad Lead como coordenador obrigatorio
O sistema SHALL ter um agente Squad Lead obrigatorio que coordena todos os demais agentes.

#### Scenario: Demanda recebida pelo Squad Lead
- **WHEN** o usuario envia mensagem sem comando no Telegram
- **THEN** a mensagem MUST ser direcionada ao Squad Lead

#### Scenario: Squad Lead conhece os agentes disponiveis
- **WHEN** o Squad Lead inicia uma demanda
- **THEN** o prompt MUST conter resumo de todos os agentes disponiveis (dominio, quando envolver, criterios de aceite) lidos dos AGENTS.md

#### Scenario: Squad Lead decide o fluxo
- **WHEN** o Squad Lead recebe uma demanda
- **THEN** ele MUST decidir quais agentes envolver, em que ordem, e invocar cada um via tools

#### Scenario: Squad Lead valida resultados
- **WHEN** um agente finaliza seu trabalho
- **THEN** o Squad Lead MUST avaliar o resultado contra os criterios de aceite do agente e decidir se aprova ou manda refazer

#### Scenario: Squad Lead manda refazer
- **WHEN** o resultado de um agente nao atende os criterios de aceite
- **THEN** o Squad Lead MUST reinvocar o agente com feedback do que precisa ser corrigido

#### Scenario: Squad Lead reporta status
- **WHEN** o usuario pergunta o andamento
- **THEN** o Squad Lead MUST informar quais agentes ja executaram, qual esta em execucao, e quais faltam

#### Scenario: Squad Lead finaliza demanda
- **WHEN** todos os agentes necessarios concluiram e os criterios foram atendidos
- **THEN** o Squad Lead MUST marcar ---DONE--- e a demanda e concluida
