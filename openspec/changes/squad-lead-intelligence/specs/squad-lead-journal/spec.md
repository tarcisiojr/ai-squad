# Spec: Squad Lead Journal

## Objetivo
Persistir o contexto de decisões do Squad Lead entre sessões, permitindo retomada inteligente de processos parados.

## Estrutura do Journal

### Caminho
```
state/{demand_id}/squad-lead-journal.json
```

### Formato
```json
{
  "demand_id": "abc-123",
  "demand_text": "Criar endpoint de login com JWT",
  "created_at": "2026-03-15T10:00:00Z",
  "updated_at": "2026-03-15T10:45:00Z",
  "current_phase": "dev_working",
  "decisions": [
    {
      "timestamp": "2026-03-15T10:00:00Z",
      "action": "delegated_to_po",
      "detail": "Demanda clara, delegada ao PO para especificação"
    },
    {
      "timestamp": "2026-03-15T10:15:00Z",
      "action": "artifacts_validated",
      "detail": "Artefatos PO OK: proposal, 2 specs com critérios, design, 5 tasks"
    },
    {
      "timestamp": "2026-03-15T10:16:00Z",
      "action": "delegated_to_dev",
      "detail": "Artefatos validados, Dev iniciado para implementar 5 tasks"
    }
  ],
  "next_expected": {
    "action": "dev_completion",
    "agent": "dev",
    "description": "Dev implementando 5 tasks. Esperado concluir em ~10min"
  },
  "context_notes": [
    "Usuário pediu JWT, não session-based auth",
    "Repo usa FastAPI, não Flask"
  ]
}
```

## Operações

### Nova tool: `read_journal(demand_id)`
Retorna o journal da demanda, ou resumo de todos os journals ativos se demand_id é None.

### Escrita automática
Engine registra no journal automaticamente:
- Quando Squad Lead delega (decisão)
- Quando check_artifacts é chamado (resultado)
- Quando agente conclui (evento)
- Quando agente falha (evento + retry info)

### Leitura no startup
Quando Squad Lead é invocado, o engine injeta no contexto:
```
## Estado Atual (Journal)
- Demanda "abc-123": Dev implementando 5 tasks (iniciado há 3min)
- Demanda "def-456": Parada em awaiting_plan_approval há 2h
```

## Integração com Heartbeat

O heartbeat loop lê journals para detectar demandas paradas:
- Journal com `next_expected.action` que não aconteceu dentro do timeout
- Journal sem atualização há mais de `STALL_TIMEOUT` (configurável, default 30min)

## Critérios de Aceite

- [ ] Journal criado automaticamente quando nova demanda chega
- [ ] Cada decisão do Squad Lead é registrada no journal
- [ ] Journal sobrevive restart do daemon
- [ ] Squad Lead recebe resumo do journal no contexto de cada invocação
- [ ] `read_journal()` retorna estado formatado para o Squad Lead
- [ ] Escrita atômica (temp + rename) como StateManager
