## Context

O ai-dev-team usa um daemon que escuta Telegram e orquestra agentes via Claude Agent SDK. Hoje o Squad Lead roda numa unica chamada SDK longa (max_turns=30) que bloqueia todo o sistema. As tools de invocacao (invoke_agent, invoke_parallel) sao apenas texto no AGENTS.md — o SDK nao as reconhece. O resultado: Squad Lead fica girando sem conseguir delegar, usuario nao consegue interagir, e eventualmente da timeout.

O Claude Agent SDK suporta MCP tools customizadas via `@tool` decorator + `create_sdk_mcp_server`. Ja temos um MCP server com report_progress. A solucao e adicionar tools reais de delegacao nesse mesmo server.

## Goals / Non-Goals

**Goals:**
- Squad Lead responde rapido (< 30s) usando chamadas SDK curtas (max_turns=3-5)
- Agentes (PO, Dev, QA) rodam em background como asyncio tasks
- Usuario pode interagir a qualquer momento, mesmo com agentes rodando
- Squad Lead tem tools MCP reais para delegar e consultar status
- Quando agente conclui, Squad Lead e automaticamente notificado para decidir proximo passo

**Non-Goals:**
- Mudar a interface do Claude Agent SDK
- Suportar multiplas demandas simultaneas (uma por vez e suficiente)
- Criar UI web — Telegram continua como unica interface
- Mudar o fluxo dos agentes (PO, Dev, QA) — so muda como sao invocados

## Decisions

### 1. MCP tools no adapter para delegacao

Adicionar ao MCP server existente (ai-dev-team-tools) tres novas tools:

- `start_agent(agent_name, task_description)` — inicia agente em background, retorna imediatamente
- `get_running_agents()` — retorna estado de todos os agentes (nome, status, tempo, resultado)
- `check_artifacts(change_name)` — executa openspec status e retorna resultado

As tools sao implementadas no adapter mas chamam callbacks do engine (mesmo padrao do report_progress). O adapter nao conhece a logica de orquestracao — apenas roteia para o engine.

Alternativa considerada: tools no engine diretamente. Descartada porque o SDK so aceita tools via MCP server registrado nas options.

### 2. Engine gerencia _running_agents

Novo dict no engine:

```python
self._running_agents: dict[str, RunningAgent] = {}

@dataclass
class RunningAgent:
    task: asyncio.Task
    agent_name: str
    demand_id: str
    started_at: float
    status: str  # "running", "done", "error"
    result: str | None
```

Quando start_agent e chamado:
1. Engine cria asyncio task que executa _run_agent_background()
2. Registra em _running_agents
3. Retorna imediatamente

Quando task conclui (via add_done_callback):
1. Atualiza status para "done" ou "error"
2. Salva resultado
3. Notifica usuario via Telegram
4. Dispara Squad Lead automaticamente com contexto do resultado

### 3. Squad Lead com max_turns baixo e contexto injetado

Squad Lead roda com max_turns=5 (em vez de 30). Cada chamada recebe:
- Mensagem do usuario
- Estado dos agentes em background
- Ultimos resultados concluidos (se houver)
- AGENTS.md do Squad Lead

Fluxo tipico:
1. User: "Criar site" → SDK call → SL chama start_agent("po",...) → responde "PO iniciado"
2. [PO roda em bg] → conclui → engine injeta resultado → SDK call automatica → SL chama start_agent("dev",...)
3. User: "Status?" → SDK call → SL chama get_running_agents() → responde com status

### 4. Daemon nao bloqueia mais

Hoje: _process_queue() pega um item, awaita run_squad_lead() (que bloqueia), so depois processa o proximo.

Novo: Cada mensagem do usuario dispara _handle_message() que:
1. Se e /status, /help → responde direto (sem SDK)
2. Se e /<agent> → inicia conversa direta com agente (background)
3. Se e texto → chama Squad Lead (SDK curta, max_turns=5)

Nao ha mais fila bloqueante. Mensagens sao processadas imediatamente. Se o Squad Lead esta sendo chamado (raro, < 30s), a mensagem espera brevemente.

### 5. Agentes background usam _agent_conversation existente

Os agentes (PO, Dev, QA) continuam usando _agent_conversation com o loop de turnos, marcadores e ask_user. A diferenca e que rodam como asyncio tasks separadas, nao dentro da chamada do Squad Lead.

Quando um agente background precisa de input do usuario (modo CHAT), ask_user continua funcionando — a mensagem do usuario e roteada para o agente correto.

### 6. Roteamento de mensagens com agente ativo

Se ha um agente em modo CHAT (esperando ask_user), mensagens do usuario DEVEM ir para ele, nao para o Squad Lead. Logica de roteamento:

1. Se _pending_agent_chat existe → mensagem vai para o agente
2. Senao → mensagem vai para o Squad Lead

## Risks / Trade-offs

**[Squad Lead pode chamar start_agent desnecessariamente]** → Mitigacao: instrucoes claras no AGENTS.md, max_turns baixo limita dano

**[Concorrencia entre agentes e mensagens]** → Mitigacao: um agente por vez (start_agent rejeita se ja ha agente rodando), roteamento claro de mensagens

**[Agente background trava sem timeout]** → Mitigacao: manter timeout existente no adapter (dev_timeout=600), asyncio.wait_for no task background

**[Mensagem do usuario vai pro agente errado]** → Mitigacao: roteamento explicito — se agente espera input, mensagem vai para ele; senao, Squad Lead
