## Why

Nos testes com o agente via Telegram, 4 problemas foram encontrados: (1) Dev diz que terminou mas tasks.md ainda tem items pendentes — o engine aceita qualquer texto como "conclusao" sem verificar; (2) Squad Lead avanca sem validar se o agente realmente cumpriu os criterios — recebe apenas "dev concluiu" sem contexto; (3) mensagens truncadas em 200 chars quando o Telegram suporta 4096; (4) atividades em paralelo corrompem estado por variaveis compartilhadas (_current_user_id). Inspirado no pattern "Ralph Wiggum" de verification loops, vamos adicionar validacao programatica antes de aceitar conclusao.

## What Changes

- **Verification loop no _on_agent_done** — antes de marcar "done", verifica programaticamente: tasks.md sem [ ] pendentes, marcador de conclusao presente, testes passando (quando aplicavel). Se incompleto, re-invoca o agente com feedback do que falta (ate MAX_RETRIES)
- **Contexto completo no _trigger_squad_lead** — passa resultado do agente, resultado da verificacao, estado do tasks.md ao Squad Lead
- **Mensagens nao-truncadas** — aumenta preview de 200 para 2000 chars (bus ja faz split em 4096)
- **Race condition corrigida** — substitui _current_user_id/_current_demand_id por parametros explicitos em cada chamada, elimina estado compartilhado entre tasks concorrentes

## Capabilities

### New Capabilities
- `agent-verification`: Verificacao programatica de conclusao de agentes (verification loop inspirado no Ralph pattern) — checa tasks.md, marcadores, testes antes de aceitar "done"

### Modified Capabilities
- `orchestrator`: _on_agent_done com verification loop, _trigger_squad_lead com contexto completo, eliminacao de race conditions
- `execution-feedback`: Preview de mensagens aumentado de 200 para 2000 chars

## Impact

- **src/orchestrator/engine.py** — _on_agent_done com verify_completion, _trigger_squad_lead com contexto, remover _current_user_id/_current_demand_id como estado de instancia
- **src/orchestrator/tools.py** — RunningAgent com user_id e demand_id para eliminar estado compartilhado
- **agents/squad-lead/AGENTS.md** — instruir SL a verificar resultado da validacao antes de avancar
