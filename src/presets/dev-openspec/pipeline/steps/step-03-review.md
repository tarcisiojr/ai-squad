---
step: "03"
name: "Revisão de Código"
type: checkpoint
agent: code-review
on_reject: implementacao
max_review_cycles: 3
---

# Step 03: Revisão de Código (Code Review)

## Inputs
- Código implementado pelo Dev (diff/commits)
- openspec/changes/<slug>/specs/**/*.md — critérios de aceite

## Expected Outputs
- Resultado contendo APROVADO ou REJEITADO
- Se rejeitado: lista de problemas específicos para correção

## Quality Gate
- [ ] Resultado contém veredicto claro (APROVADO ou REJEITADO)
- [ ] Se rejeitado, contém lista de problemas específicos

## Veto Conditions
- Resultado sem veredicto (nem APROVADO nem REJEITADO)
