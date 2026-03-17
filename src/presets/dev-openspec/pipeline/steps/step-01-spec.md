---
step: "01"
name: "Especificação"
type: checkpoint
agent: po
execution: subagent
model_tier: powerful
---

# Step 01: Especificação (PO)

## Inputs
- Mensagem do usuário descrevendo a demanda

## Expected Outputs
- openspec/changes/<slug>/proposal.md
- openspec/changes/<slug>/design.md
- openspec/changes/<slug>/tasks.md
- openspec/changes/<slug>/specs/**/*.md

## Quality Gate
- [ ] proposal.md existe e tem mais de 50 bytes
- [ ] design.md existe e tem mais de 50 bytes
- [ ] tasks.md existe e tem pelo menos 3 itens
- [ ] Pelo menos 1 spec em specs/ com critérios de aceite (checklist)

## Veto Conditions
- tasks.md com menos de 3 itens
- Spec sem nenhum critério de aceite (sem checklist - [ ])
