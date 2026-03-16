# Spec: Artifact-Based Completion

## Objetivo
Substituir o sistema de markers textuais (`---SPEC_READY---`, `---DONE---`, `---QA_DONE---`) por detecção de conclusão baseada em artefatos reais, usando o Criteria Gate como source of truth.

## O que é removido

| Componente | Localização | Ação |
|------------|-------------|------|
| Markers no output | PO: `---SPEC_READY---` | Remover do AGENTS.md do PO |
| | Dev: `---DONE---` | Remover do AGENTS.md do Dev |
| | QA: `---QA_DONE---` | Remover do AGENTS.md do QA |
| Regex de detecção | `engine.py: _verify_completion()` | Substituir por Criteria Gate |
| Constantes | `DONE_MARKERS` dict no engine | Remover |
| Retry genérico | "marker não encontrado, tente novamente" | Substituir por feedback específico |

## O que substitui

### `_verify_completion()` novo comportamento

```python
async def _verify_completion(self, agent_name: str, resultado: str) -> VerificationResult:
    """Verifica conclusão via artefatos, não markers."""

    if agent_name == "po":
        return await self._check_po_completion()
    elif agent_name == "dev":
        return await self._check_dev_completion()
    elif agent_name == "qa":
        return await self._check_qa_completion()
```

### Verificação por agente

**PO concluiu quando:**
- proposal.md existe
- specs/ tem pelo menos 1 spec
- Specs contêm critérios de aceite (`- [ ]`)
- design.md existe
- tasks.md existe com ≥ 3 itens

**Dev concluiu quando:**
- tasks.md sem itens pendentes (`- [ ]`)
- Git status limpo (sem arquivos não commitados)

**QA concluiu quando:**
- QA report existe
- Report contém `Resultado: APROVADO`

### Retry com feedback específico

Quando verificação falha, o retry inclui exatamente o que falta:

```
# Antes (marker-based)
"Não detectei o marker ---SPEC_READY---. Por favor, finalize o trabalho e inclua o marker."

# Depois (artifact-based)
"Trabalho incompleto. Problemas encontrados:
- specs/auth/spec.md não tem critérios de aceite (adicione checklist com '- [ ]')
- tasks.md tem apenas 1 item (mínimo 3)
Por favor, corrija e finalize."
```

## Impacto nos AGENTS.md dos agentes

### PO (agents/po/AGENTS.md)
- Remover: instrução para escrever `---SPEC_READY---` ao final
- Manter: instrução para criar proposal, specs, design, tasks

### Dev (agents/dev/AGENTS.md)
- Remover: instrução para escrever `---DONE---` ao final
- Manter: instrução para marcar tasks como `[x]` e commitar

### QA (agents/qa/AGENTS.md)
- Remover: instrução para escrever `---QA_DONE---` ao final
- Manter: instrução para gerar report com `Resultado: APROVADO/REJEITADO`

## Compatibilidade

- Se um agente ainda produzir markers por hábito, eles são ignorados (sem erro)
- O Criteria Gate é a única fonte de verdade para conclusão
- MAX_RETRIES (2) permanece igual

## Critérios de Aceite

- [ ] Nenhum marker textual é necessário para detectar conclusão
- [ ] `_verify_completion()` usa Criteria Gate em vez de regex de markers
- [ ] PO concluído = artefatos openspec válidos e completos
- [ ] Dev concluído = tasks.md sem pendências + git limpo
- [ ] QA concluído = report com APROVADO
- [ ] Retry envia feedback específico (o que falta, não "coloque o marker")
- [ ] AGENTS.md do PO, Dev e QA não mencionam markers
- [ ] Markers residuais no output são ignorados (não causam erro)
