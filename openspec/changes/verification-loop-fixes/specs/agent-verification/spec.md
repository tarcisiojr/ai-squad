## ADDED Requirements

### Requirement: Verificacao programatica de conclusao (verification loop)
O engine SHALL verificar programaticamente se um agente realmente concluiu antes de marcar como "done".

#### Scenario: Dev conclui com tasks pendentes
- **WHEN** o Dev retorna resultado mas tasks.md ainda tem `- [ ]` pendentes
- **THEN** o engine MUST marcar como "incomplete" e re-invocar o Dev com feedback das tasks faltantes

#### Scenario: Dev conclui com todas tasks marcadas
- **WHEN** o Dev retorna resultado e todas as tasks em tasks.md estao `- [x]`
- **THEN** o engine MUST marcar como "done" e notificar Squad Lead

#### Scenario: Agente conclui sem marcador de conclusao
- **WHEN** um agente retorna resultado sem o marcador esperado (---DONE---, ---SPEC_READY---, ---QA_DONE---)
- **THEN** o engine MUST marcar como "incomplete" e re-invocar com feedback pedindo o marcador

#### Scenario: Agente conclui com marcador presente
- **WHEN** um agente retorna resultado com o marcador de conclusao correto
- **THEN** a verificacao do marcador MUST passar

#### Scenario: Limite de re-tentativas
- **WHEN** um agente falha na verificacao MAX_RETRIES vezes consecutivas
- **THEN** o engine MUST parar de re-invocar, marcar como "incomplete", e notificar o usuario sobre a falha

### Requirement: Verificacao especifica por tipo de agente
O engine SHALL aplicar verificacoes especificas para cada tipo de agente.

#### Scenario: Verificacao do PO
- **WHEN** o PO conclui
- **THEN** o engine MUST verificar que o marcador ---SPEC_READY--- esta presente

#### Scenario: Verificacao do Dev
- **WHEN** o Dev conclui
- **THEN** o engine MUST verificar que o marcador ---DONE--- esta presente e que tasks.md nao tem `- [ ]` pendentes

#### Scenario: Verificacao do QA
- **WHEN** o QA conclui
- **THEN** o engine MUST verificar que o marcador ---QA_DONE--- esta presente
