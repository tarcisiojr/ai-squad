# Design: Message Deduplication

## Visão Geral

```
ANTES (3 caminhos → repetição)          DEPOIS (canal único)
─────────────────────────────           ─────────────────────────
                                        
Agente                                  Agente
  ├─► report_progress ──► 👤            ├─► report_progress ──► Squad Lead (interno)
  ├─► on_agent_done ────► 👤            └─► resultado ─────────► Squad Lead (interno)
  └─► Squad Lead ───────► 👤                                        │
       (re-triggered)                              ┌────────────────┘
                                                   ▼
                                              Squad Lead
                                                   │
                                          ┌────────┼────────┐
                                          ▼        ▼        ▼
                                       status   forward   decisão
                                       leve    ou resume  próx step
                                          │        │        │
                                          └────────┼────────┘
                                                   ▼
                                                  👤 Usuário
```

## Mudanças por Arquivo

### 1. `src/orchestrator/agent_runner.py`

**on_agent_done (linhas 313-324):**

Remover o envio direto ao usuário e manter apenas o trigger do Squad Lead:

```python
# REMOVER: envio direto do resultado ao usuário (linhas 313-318)
# await self._ctx.message_bus.send_message(
#     user_id, f"Concluido!\n\n{preview}", sender=label, ...
# )

# MANTER: trigger do Squad Lead, mas com resultado completo como contexto
await self._on_squad_lead_trigger(
    running,
    f"RESULTADO DO AGENTE (não repita literalmente, apresente de forma concisa):\n{preview}",
)
```

**Histórico de conversa (linhas 304-311):**

Marcar a mensagem como interna para que o prompt do Squad Lead saiba que o usuário ainda não viu:

```python
self._ctx.conversation.save_message(
    running.demand_id,
    "internal",  # era "assistant" — agora é canal interno
    f"{agent_name} concluiu: {preview[:500]}",
    agent_name=agent_name,
)
```

### 2. `src/orchestrator/engine.py`

**_handle_progress (linhas 245-263):**

Trocar envio direto por armazenamento interno + status leve:

```python
async def _handle_progress(self, agent_name: str, message: str) -> None:
    user_id = self._resolve_user_id(agent_name)
    if not user_id:
        return

    # Armazena progresso internamente no RunningAgent
    running = self._agent_runner._running_agents.get(agent_name)
    if running:
        if not hasattr(running, 'progress_log'):
            running.progress_log = []
        running.progress_log.append(message)

    # Envia status leve ao usuário (apenas 1x, na primeira chamada)
    if running and len(running.progress_log) == 1:
        label = self._get_agent_label(agent_name)
        thread_id = self._resolve_thread_id(agent_name)
        await self._message_bus.send_message(
            user_id,
            f"⚙️ {label} trabalhando...",
            sender=label,
            thread_id=thread_id,
        )
```

**_build_squad_lead_prompt (linhas 541-621):**

Adicionar instrução anti-repetição no prompt:

```python
# Após injetar o contexto do evento (linha ~617)
prompt_parts.append("""
REGRA DE COMUNICAÇÃO:
- Você é o porta-voz do time. Apresente resultados de forma CONCISA.
- NÃO repita literalmente o que o agente produziu. Resuma em 1-3 frases.
- Separe RESULTADO (o que foi feito) de DECISÃO (próximo passo).
- Se o resultado for autoexplicativo e curto, pode repassar direto.
- Se o resultado for longo ou técnico, resuma o essencial para o usuário.
- Formato ideal: "[O que aconteceu em 1 frase]. [Próximo passo]."
""")
```

**_trigger_squad_lead_for_agent (linhas 506-529):**

Incluir progress_log do agente como contexto interno:

```python
# Antes de chamar run_squad_lead, montar contexto com progresso
progress_context = ""
if hasattr(running, 'progress_log') and running.progress_log:
    progress_context = "\nProgresso reportado pelo agente:\n" + "\n".join(
        f"- {p}" for p in running.progress_log[-5:]  # últimos 5
    )

event_with_progress = f"{event_context}{progress_context}"
await self.run_squad_lead(demand_id, user_id, event_with_progress, thread_id=thread_id)
```

### 3. `src/adapters/mcp_tools_server.py`

**report_progress tool description (linhas 113-124):**

Atualizar descrição para refletir novo comportamento:

```python
{
    "name": "report_progress",
    "description": (
        "Reporta progresso internamente. O Squad Lead recebe seu progresso "
        "e decide o que comunicar ao usuario. Use para registrar etapas "
        "importantes do seu trabalho."
    ),
    ...
}
```

### 4. `src/orchestrator/tools.py`

**RunningAgent model:**

Adicionar campo para progress_log:

```python
@dataclass
class RunningAgent:
    # ... campos existentes ...
    progress_log: list[str] = field(default_factory=list)
```

## Fluxo Completo (após mudanças)

```
1. Usuário pede tarefa
2. Squad Lead delega: "Dev Backend, analise o código"
3. Dev Backend inicia execução
4. Dev Backend chama report_progress("Analisando 15 arquivos")
   → Internamente: salvo no RunningAgent.progress_log
   → Usuário vê: "⚙️ Dev Backend trabalhando..."
5. Dev Backend chama report_progress("Encontrei 3 issues")
   → Internamente: salvo no progress_log (sem novo envio ao usuário)
6. Dev Backend conclui com resultado completo
   → NÃO é enviado ao usuário
   → Squad Lead é triggered com resultado + progress_log
7. Squad Lead processa e envia ao usuário:
   "Dev Backend encontrou 3 issues no módulo de autenticação.
    Vou pedir pro QA validar as correções."
```

## Decisões de Design

- **progress_log no RunningAgent** — simples, sem novo modelo. Log é efêmero (vive enquanto o agente roda)
- **Status leve apenas 1x** — evita spam de "trabalhando..." para agentes que fazem muitos report_progress
- **Instrução no prompt vs lógica em código** — optamos por instrução no prompt para flexibilidade (Squad Lead decide forward vs resume baseado no conteúdo)
- **Mensagem interna no histórico** — marca como "internal" para que o Squad Lead saiba que o usuário não viu aquele conteúdo
- **Limite de 5 progress no contexto** — evita explodir o prompt com logs muito longos

## Riscos

- **Squad Lead pode ainda repetir** — depende da instrução no prompt ser efetiva. Mitigação: testar com diferentes LLMs e ajustar wording
- **Perda de visibilidade** — usuário não vê mais progresso detalhado em tempo real. Mitigação: status leve confirma que agente está ativo
- **Latência percebida** — resultado demora mais (espera Squad Lead processar). Mitigação: status leve reduz ansiedade
