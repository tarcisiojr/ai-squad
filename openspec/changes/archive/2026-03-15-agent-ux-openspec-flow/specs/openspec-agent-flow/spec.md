## ADDED Requirements

### Requirement: Ciclo de demanda via OpenSpec
O engine SHALL seguir o framework OpenSpec para o ciclo de vida de demandas.

#### Scenario: PO gera proposal
- **WHEN** o PO finaliza a especificação (marcador SPEC_READY)
- **THEN** o engine MUST salvar o resultado como `specs/<demand-id>/proposal.md` no workspace

#### Scenario: Dev lê specs antes de implementar
- **WHEN** o Dev inicia implementação
- **THEN** o engine MUST incluir o conteúdo de `specs/<demand-id>/proposal.md` no contexto do prompt

#### Scenario: Dev salva design
- **WHEN** o Dev marca ---DONE---
- **THEN** o engine MUST salvar o design técnico como `specs/<demand-id>/design.md` no workspace

#### Scenario: QA valida contra specs
- **WHEN** o QA inicia validação
- **THEN** o engine MUST incluir proposal.md e design.md da demanda no contexto do prompt do QA

### Requirement: Artefatos como documentação viva
Os artefatos gerados SHALL permanecer no repositório como histórico versionável.

#### Scenario: Artefatos commitáveis
- **WHEN** o ciclo de demanda é concluído
- **THEN** os artefatos em `specs/<demand-id>/` MUST ser arquivos markdown válidos e commitáveis no git
