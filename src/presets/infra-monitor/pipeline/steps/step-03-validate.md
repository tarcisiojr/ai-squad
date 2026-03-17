---
step: "03"
name: "Validação"
type: checkpoint
agent: validator
---

# Step 03: Validação

## Inputs
- Log de ações de remediação
- Métricas atuais dos serviços

## Expected Outputs
- Confirmação de que métricas normalizaram
- Relatório de validação

## Quality Gate
- [ ] Métricas dos serviços afetados verificadas
- [ ] Confirmação de normalização

## Veto Conditions
- Métricas ainda anormais
