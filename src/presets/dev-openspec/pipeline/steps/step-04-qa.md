---
step: "04"
name: "QA"
type: agent
agent: qa
model_tier: powerful
---

# Step 04: QA (Quality Assurance)

## Inputs
- Código implementado e aprovado pelo Code Review
- openspec/changes/<slug>/specs/**/*.md — critérios de aceite para validação

## Expected Outputs
- Relatório de QA com resultado dos testes
- Validação dos critérios de aceite das specs

## Quality Gate
- [ ] Relatório de QA gerado
- [ ] Critérios de aceite das specs verificados

## Veto Conditions
- Testes falhando
- Critérios de aceite não atendidos
