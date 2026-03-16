# Spec: Heartbeat Loop

## Objetivo
Daemon verifica periodicamente demandas paradas e aciona o Squad Lead para retomar automaticamente.

## Mecanismo

### Timer
- Intervalo configurável: `heartbeat_interval` em platform.yaml (default: 300 segundos / 5 min)
- Roda como asyncio task no daemon, junto com o polling do Telegram

### Lógica do Heartbeat

```python
async def _heartbeat_loop():
    while not self._shutdown:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        stalled = self._find_stalled_demands()
        for demand in stalled:
            await self._resume_stalled_demand(demand)
```

### Detecção de Demandas Paradas

Uma demanda é considerada "parada" (`stalled`) quando:

| Condição | Descrição |
|----------|-----------|
| Estado intermediário | Não é `idle` nem `done` |
| Sem agente rodando | Nenhum RunningAgent ativo para essa demand_id |
| Timeout de inatividade | Última atualização do journal > `STALL_TIMEOUT` |
| Sem ação pendente do usuário | Estado NÃO é `awaiting_plan_approval` nem `awaiting_pr_approval` |

**Importante**: Demandas em `awaiting_*_approval` NÃO são consideradas paradas — estão esperando o usuário. O heartbeat pode enviar um **lembrete** ao usuário depois de `REMINDER_TIMEOUT` (default: 1h).

### Ação de Retomada

```python
async def _resume_stalled_demand(demand):
    journal = self._journal.read(demand.demand_id)
    next_action = journal["next_expected"]

    # Reativa o Squad Lead com contexto da retomada
    await self.engine.run_squad_lead(
        demand_id=demand.demand_id,
        user_id=demand.user_id,
        demand_text=f"RETOMADA AUTOMÁTICA: {next_action['description']}"
    )
```

### Lembretes para Aprovação

Para demandas em `awaiting_*_approval`:
```python
if demand.state in APPROVAL_STATES and demand.stalled_since > REMINDER_TIMEOUT:
    await self._bus.send_message(
        demand.user_id,
        f"⏳ Lembrete: demanda '{demand.demand_text}' aguarda sua aprovação."
    )
```

## Configuração

```yaml
# platform.yaml
heartbeat:
  enabled: true
  interval: 300          # Segundos entre verificações
  stall_timeout: 1800    # Segundos para considerar parada (30min)
  reminder_timeout: 3600 # Segundos para lembrete de aprovação (1h)
  max_auto_retries: 3    # Máximo de retomadas automáticas por demanda
```

## Proteções

- **Max retries**: Após N retomadas automáticas, notifica usuário e para
- **Cooldown**: Não retomar a mesma demanda em menos de `stall_timeout`
- **Approval protection**: Nunca auto-aprovar — apenas lembrar o usuário
- **Shutdown-safe**: Heartbeat para gracefully no SIGTERM

## Critérios de Aceite

- [ ] Heartbeat roda a cada `interval` segundos no daemon
- [ ] Detecta demandas paradas (estado intermediário + sem agente + timeout)
- [ ] Retoma demanda parada acionando Squad Lead com contexto
- [ ] NÃO retoma demandas em awaiting_*_approval (envia lembrete)
- [ ] Respeita max_auto_retries por demanda
- [ ] Configurável via platform.yaml
- [ ] Para gracefully no shutdown
- [ ] Lembrete enviado ao usuário para aprovações pendentes > reminder_timeout
