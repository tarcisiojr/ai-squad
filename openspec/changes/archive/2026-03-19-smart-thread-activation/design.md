## Context

O sistema atual processa todas as mensagens recebidas pelo MessageBus sem filtro — em grupos/espaços, o bot responde a tudo. Ferramentas do mercado (Microsoft Copilot, Slack agents, Google Chat) usam o padrão mention-based em grupos e all em DMs. Nossos usuários trabalham com threads como unidade de incidente, onde humanos e bot podem coexistir.

## Goals / Non-Goals

**Goals:**
- Filtro de ativação configurável (`mention`/`all`/`command`) por espaço/grupo
- Rastreamento de estado por thread (active → standby → convocado)
- Transição automática quando humano entra na thread
- Persistência do estado de threads (sobrevive a restarts)
- Tempos configuráveis com defaults sensatos
- Re-convocação via @mention em qualquer momento

**Non-Goals:**
- Detecção semântica de "humano assumiu" via IA (complexo demais — usamos heurística simples)
- Integração com sistemas de ticketing externos
- Suporte a múltiplos bots no mesmo espaço

## Decisions

### 1. Activation mode na camada de messaging

**Decisão:** Cada MessageBus implementa filtro de menção/comando no ponto de recebimento, antes de invocar o callback do daemon.

**Alternativa considerada:** Filtrar no daemon — descartada porque cada provider tem mecanismo diferente de menção (GChat: annotations, Telegram: entities com @username).

**Configuração:**
```yaml
# config.yaml
activation_mode: mention   # mention | all | command
```

**Comportamento por tipo de chat:**
- DM (1:1): sempre `all`, ignora configuração
- Grupo/espaço: usa `activation_mode` configurado

**Por provider:**
- GChat: a API já filtra nativamente — em espaços, só entrega mensagens com @mention. Se `activation_mode: all`, usamos polling de todas as mensagens
- Telegram: filtra por `entities` do tipo `mention` com `@bot_username`
- CLI: sempre `all` (é 1:1 por natureza)

### 2. ThreadTracker como componente do orchestrator

**Decisão:** Novo módulo `src/orchestrator/thread_tracker.py` com classe `ThreadTracker` que gerencia estado por thread_id.

**Estados:**
```
INACTIVE  →  ACTIVE  →  STANDBY  →  ACTIVE (re-convocado)
                ↑                       ↑
                └── @mention ───────────┘
```

- `INACTIVE`: bot nunca foi chamado nessa thread
- `ACTIVE`: bot lidera (respondendo a tudo na thread)
- `STANDBY`: humano respondeu, bot recuou
- Qualquer @mention → volta a `ACTIVE`

**Regra de transição para STANDBY:**
- Bot está ACTIVE na thread
- Mensagem de um humano (não bot) chega na thread
- Mensagem NÃO menciona o bot
- → Bot entra em STANDBY, envia mensagem de handoff

### 3. Persistência via atomic_write

**Decisão:** Estado das threads persistido em `state/threads.json` usando `write_json_atomic` existente. Carregado no startup do daemon.

**Formato:**
```json
{
  "thread_abc123": {
    "state": "active",
    "activated_at": "2026-03-19T14:00:00Z",
    "last_bot_message": "2026-03-19T14:05:00Z",
    "last_human_message": null,
    "human_who_took_over": null
  }
}
```

**Limpeza:** threads com `last_activity` > `inactive_thread_ttl` são removidas no startup.

### 4. Tempos configuráveis

**Decisão:** Seção `thread_tracking` no config.yaml com defaults:

```yaml
thread_tracking:
  standby_timeout: 1800        # 30min — bot oferece ajuda se humano sumiu
  inactive_thread_ttl: 86400   # 24h — limpa threads inativas
  handoff_message: true        # envia "Fulano assumiu" ao recuar
```

### 5. Pending reply respeita activation mode

**Decisão:** Se o bot fez uma pergunta (approval/ask_user) e está aguardando resposta, a próxima mensagem na thread é capturada INDEPENDENTE de menção. O pending_reply tem prioridade sobre o activation_mode.

**Justificativa:** Se o bot perguntou "Aprovado?", o usuário não deveria precisar digitar "@bot Aprovado".

### 6. Integração com learn_lesson

**Decisão:** Não é necessária mudança no learn_lesson — o bot já pode ser convocado via @mention no final de uma thread para registrar aprendizados. O fluxo é:

```
👤 "@ai-squad registra: causa foi pgbouncer com >200 conexões"
🤖 Bot processa via Squad Lead → learn_lesson(...)
```

Isso já funciona com a arquitetura atual — o @mention reativa o bot na thread.

## Risks / Trade-offs

- **[Falso handoff]** Humano faz comentário casual na thread mas não está "assumindo" → Bot recua desnecessariamente → Mitigação: @mention re-ativa instantaneamente, e a mensagem de handoff deixa claro como chamar de volta
- **[Persistência em escala]** Muitas threads simultâneas podem crescer o threads.json → Mitigação: TTL de 24h limpa threads inativas automaticamente
- **[GChat polling vs events]** Se mudarmos para usar o modelo nativo de eventos do GChat (só menções), perdemos a capacidade de `activation_mode: all` → Trade-off aceitável, quem quer `all` pode configurar
- **[Race condition]** Mensagem de humano e do bot chegam quase simultaneamente → Mitigação: check de timestamp antes de transitar para standby
