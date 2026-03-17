---
step: "02"
name: "Implementação"
type: agent
agents: [dev-backend, dev-frontend]
execution: background
model_tier: powerful
---

# Step 02: Implementação (Dev)

## Inputs
- openspec/changes/<slug>/tasks.md — lista de tarefas a implementar
- openspec/changes/<slug>/design.md — design técnico
- openspec/changes/<slug>/specs/**/*.md — especificações detalhadas

## Expected Outputs
- Código implementado no workspace
- Todas as tasks marcadas como [x] no tasks.md
- Testes unitários passando

## Quality Gate
- [ ] Todas as tasks em tasks.md marcadas como concluídas [x]
- [ ] Nenhuma task pendente [ ] restante

## Veto Conditions
- Mais de 50% das tasks ainda pendentes
