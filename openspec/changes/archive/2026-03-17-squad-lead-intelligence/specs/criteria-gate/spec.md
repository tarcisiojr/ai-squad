# Spec: Criteria Gate

## Objetivo
Evoluir `check_artifacts()` de uma verificação de existência para uma **validação de qualidade e completude**.

## Validações por Fase

### Transição PO → Dev (check antes de start_agent("dev"))

| Validação | Como verificar | Obrigatório |
|-----------|---------------|-------------|
| proposal.md existe | File exists | Sim |
| specs/ tem pelo menos 1 spec | Dir has .md files | Sim |
| Specs têm critérios de aceite | Regex: `- \[ \]` em specs/*.md | Sim |
| design.md existe | File exists | Sim |
| tasks.md existe e tem tarefas | File exists + regex `- \[ \]` | Sim |
| tasks.md não está vazio | Pelo menos 3 itens `- [ ]` | Sim |

### Transição Dev → QA (check antes de start_agent("qa"))

| Validação | Como verificar | Obrigatório |
|-----------|---------------|-------------|
| tasks.md sem pendências | Regex: nenhum `- [ ]` restante | Sim |
| Código commitado | `git status --porcelain` clean | Sim |
| Testes passando | `pytest` exit code 0 | Sim |

### Transição QA → Done

| Validação | Como verificar | Obrigatório |
|-----------|---------------|-------------|
| QA report existe | File exists em artifacts | Sim |
| Resultado APROVADO | Regex: `Resultado: APROVADO` | Sim |
| Cobertura ≥ 80% | Regex: `Cobertura: (\d+)%` ≥ 80 | Recomendado |

## Retorno enriquecido

```json
{
  "passed": false,
  "phase": "po_to_dev",
  "checks": [
    {"name": "proposal_exists", "passed": true, "detail": "proposal.md encontrado"},
    {"name": "specs_have_criteria", "passed": false, "detail": "specs/auth/spec.md não tem critérios de aceite (nenhum '- [ ]' encontrado)"},
    {"name": "tasks_minimum", "passed": true, "detail": "tasks.md tem 7 itens"}
  ],
  "summary": "5/6 validações passaram. Faltam critérios de aceite em specs/auth/spec.md",
  "action": "Re-delegue ao PO para adicionar critérios de aceite"
}
```

## Comportamento do Squad Lead

Quando `check_artifacts()` falha:
1. NÃO avança para próxima fase
2. Re-delega ao agente atual com feedback específico: "Faltam critérios de aceite em specs/auth/spec.md"
3. Informa usuário: "Artefatos incompletos, PO corrigindo: faltam critérios de aceite"

## Critérios de Aceite

- [ ] check_artifacts valida existência E conteúdo dos artefatos
- [ ] Specs sem critérios de aceite (`- [ ]`) falham a validação
- [ ] tasks.md vazio ou com menos de 3 itens falha
- [ ] Retorno inclui detalhes de cada validação individual
- [ ] Squad Lead re-delega automaticamente quando validação falha
- [ ] Feedback específico é passado ao agente re-delegado
