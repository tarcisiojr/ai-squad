## ADDED Requirements

### Requirement: Risk Reviewer questiona a tese como devil's advocate
O Risk Reviewer SHALL analisar a tese de investimento e questionar sua robustez antes de aprovar.

#### Scenario: Valida coerência dos dados
- **WHEN** Risk Reviewer recebe a tese de investimento
- **THEN** SHALL verificar se recomendação é coerente com os dados apresentados
- **THEN** SHALL verificar se dados citados são recentes (últimos 3 meses)
- **THEN** SHALL verificar se fontes foram citadas

#### Scenario: Questiona viés de confirmação
- **WHEN** Risk Reviewer analisa a tese
- **THEN** SHALL verificar se a análise considerou cenários adversos
- **THEN** SHALL verificar se riscos foram adequadamente ponderados
- **THEN** SHALL verificar se há viés (ex: só dados positivos selecionados)

#### Scenario: Aprovação
- **WHEN** tese é coerente, dados são recentes e riscos foram cobertos
- **THEN** SHALL aprovar com resultado contendo "APROVADO"

#### Scenario: Rejeição com feedback
- **WHEN** tese tem falhas (dados inconsistentes, riscos ignorados, viés)
- **THEN** SHALL rejeitar com resultado contendo "REJEITADO"
- **THEN** SHALL listar problemas específicos para correção pelo Strategist
