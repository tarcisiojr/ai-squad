## ADDED Requirements

### Requirement: Pipeline de 3 steps com pesquisa paralela
O pipeline SHALL definir 3 steps: research (paralelo), thesis (sequencial), risk-review (checkpoint com on_reject).

#### Scenario: Step research roda 3 agentes em paralelo
- **WHEN** pipeline inicia para um ativo
- **THEN** step research SHALL iniciar analyst, quant e macro em background (paralelo)
- **THEN** pipeline SHALL aguardar os 3 concluírem antes de avançar

#### Scenario: Step thesis consolida após pesquisa
- **WHEN** step research conclui (3 agentes finalizaram)
- **THEN** step thesis SHALL iniciar strategist como subagent
- **THEN** strategist SHALL ter acesso aos 3 relatórios gerados

#### Scenario: Step risk-review com loop de revisão
- **WHEN** step thesis conclui
- **THEN** step risk-review SHALL iniciar risk-reviewer como checkpoint
- **WHEN** risk-reviewer rejeita
- **THEN** pipeline SHALL voltar ao step thesis (on_reject)
- **WHEN** risk-reviewer aprova
- **THEN** pipeline SHALL concluir e entregar ao usuário

#### Scenario: Máximo de 2 ciclos de revisão
- **WHEN** risk-reviewer rejeita pela segunda vez
- **THEN** pipeline SHALL escalar para o usuário decidir (max_review_cycles: 2)
