## Context

Nos testes reais via Telegram, agentes reportam conclusao sem realmente ter terminado. O engine aceita qualquer texto como "done", o Squad Lead avanca sem verificar, mensagens sao truncadas em 200 chars, e atividades paralelas corrompem estado compartilhado. Inspirado no pattern Ralph Wiggum (verification loops), vamos adicionar checagem programatica.

## Goals / Non-Goals

**Goals:**
- Agentes so sao marcados "done" apos verificacao programatica passar
- Re-invocacao automatica quando verificacao falha (ate MAX_RETRIES)
- Squad Lead recebe contexto completo para tomar decisao informada
- Mensagens de conclusao com conteudo util (nao truncado)
- Atividades paralelas isoladas sem race conditions

**Non-Goals:**
- Verificacao subjetiva (qualidade do codigo, UX) — so verificacoes programaticas
- Executar testes automaticos do projeto (complexo demais para v1)
- Mudar o fluxo de delegacao async (ja implementado)

## Decisions

### 1. verify_completion() por tipo de agente

Funcao que recebe (agent_name, resultado, workspace) e retorna VerificationResult(passed, details):

- **PO**: verifica marcador ---SPEC_READY--- presente
- **Dev**: verifica marcador ---DONE--- E tasks.md sem `- [ ]` pendentes
- **QA**: verifica marcador ---QA_DONE--- presente
- **Outros**: verifica apenas se resultado nao esta vazio

Para verificar tasks.md, o engine le o arquivo no workspace e conta `- [ ]` vs `- [x]`. O caminho do tasks.md e inferido da change ativa (openspec/changes/*/tasks.md).

### 2. Re-invocacao com feedback (Ralph loop)

Quando verificacao falha, o engine re-invoca o agente com prompt de feedback:

```
Voce reportou conclusao mas a verificacao falhou:
- tasks.md: 3/7 tasks pendentes (- [ ])
- Marcador ---DONE--- ausente

Continue o trabalho e conclua as tasks faltantes.
```

Maximo MAX_RETRIES = 2 (total 3 tentativas). Apos MAX_RETRIES, marca como "incomplete" e notifica usuario.

### 3. Contexto completo no _trigger_squad_lead

Ao disparar Squad Lead apos agente concluir, incluir:

- Resultado completo do agente (nao preview)
- VerificationResult (passed/failed + detalhes)
- Estado de todos os agentes (_get_running_agents_status)

### 4. Preview aumentado para 2000 chars

Mudar `resultado[:200]` para `resultado[:2000]` na notificacao ao usuario. O bus de Telegram ja faz split automatico em 4096 chars.

### 5. Eliminar _current_user_id/_current_demand_id

Mover user_id e demand_id para RunningAgent. Cada agente background carrega seu proprio contexto. As callbacks (report_progress, etc.) recebem esses valores do RunningAgent, nao de variaveis de instancia compartilhadas.

## Risks / Trade-offs

**[Re-invocacao pode gerar loops infinitos]** → Mitigacao: MAX_RETRIES = 2, total 3 tentativas no maximo

**[Verificacao de tasks.md pode falhar se formato diferente]** → Mitigacao: regex simples `- \[ \]` e `- \[x\]`, aceita variantes

**[Custo de re-invocacao]** → Mitigacao: maximo 2 re-invocacoes, prompt curto e focado no que falta
