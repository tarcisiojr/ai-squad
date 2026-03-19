## Context

Hoje o daemon usa `_squad_lead_conversation_id = "squad-lead-session"` como ID fixo para todas as interações com o Squad Lead. Isso faz com que conversas, journals e pipeline states de demandas diferentes sejam armazenados juntos. A infra de baixo nível (StateManager, JournalStore, ConversationStore, PipelineExecutor) já suporta isolamento por `demand_id` — o gap está na camada de roteamento (daemon) e contexto (prompt_builder).

O Telegram Bot API oferece Forum Topics nativamente em supergrupos, com `message_thread_id` para rotear mensagens para tópicos específicos e `createForumTopic` para criar novos tópicos programaticamente.

## Goals / Non-Goals

**Goals:**
- Cada demanda SHALL ter seu próprio tópico no Telegram (quando em grupo-fórum)
- Mensagens em um tópico SHALL ser roteadas diretamente para o demand_id correspondente
- Respostas de agentes (progresso, resultado, erro) SHALL ir para o tópico correto
- O Tópico Geral SHALL funcionar como canal de conversa livre com o Squad Lead + dashboard de demandas
- DMs e grupos sem fórum SHALL manter o comportamento atual (fallback gracioso)
- Handlers SHALL distinguir `chat_id` (onde) de `user_id` (quem)

**Non-Goals:**
- Permissões por usuário (quem pode criar/aprovar demandas) — change futura
- Roles de usuário (admin, dev, viewer) — change futura
- Migração de demandas existentes em "squad-lead-session" para tópicos
- Suporte a outros canais (Slack threads, Discord channels) — mesma abstração, mas implementação futura
- Notificações cross-tópico (ex: "sua demanda no tópico X terminou" no tópico geral)

## Decisions

### D1: Tópico como unidade de isolamento de demanda

Cada nova demanda criada pelo Squad Lead (via `start_agent` MCP tool) gera automaticamente um Forum Topic no Telegram. O título do tópico usa o avatar do agente + descrição curta da demanda.

**Alternativas consideradas:**
- *Inferência por LLM* — Squad Lead tenta adivinhar qual demanda baseado no texto. Descartado: frágil, sem garantias, piora com multi-usuário. Nenhum framework de referência usa essa abordagem.
- *Comandos explícitos do usuário* (`/demanda login ...`) — funciona mas adiciona fricção. Descartado: UX inferior, Forum Topics resolve sem exigir nada do usuário.

**Rationale:** Alinhado com o padrão do mercado (OpenClaw usa canais/tópicos, LangGraph usa thread_id explícito). Isolamento é estrutural, não inferido.

### D2: Mapeamento thread_id ↔ demand_id persistido em JSON

Novo arquivo `state/thread-demands.json` mapeia `thread_id → demand_id` e `demand_id → thread_id`. Carregado na inicialização do daemon, atualizado atomicamente a cada nova demanda.

```json
{
  "thread_to_demand": {"123": "login-oauth-a1b2", "456": "dashboard-metr-z3"},
  "demand_to_thread": {"login-oauth-a1b2": "123", "dashboard-metr-z3": "456"}
}
```

**Alternativas consideradas:**
- *SQLite* — mais robusto mas adiciona dependência para um mapeamento simples. Descartado: JSON com atomic_write já é usado em todo o projeto.
- *Em memória apenas* — perde mapeamento no restart. Descartado: demandas sobrevivem a restarts, mapeamento também precisa.

**Rationale:** Consistente com o padrão do projeto (state.py, journal.py, conversation.py todos usam JSON + atomic_write).

### D3: Tópico Geral = conversa livre, sem demand_id

Mensagens no Tópico Geral (thread_id=None ou thread_id do General) vão para o Squad Lead com um ID de sessão efêmero (sem pipeline, sem journal). O Squad Lead pode:
- Responder perguntas genéricas
- Listar demandas ativas
- Criar novas demandas (que geram tópicos novos)

**Rationale:** Separa conversa casual de trabalho estruturado. O Squad Lead no Tópico Geral é um "concierge", nos tópicos de demanda é um "gerente de projeto".

### D4: Fallback transparente para modo flat

Se `update.message.message_thread_id` é None e o chat não é um grupo-fórum, o daemon volta ao comportamento atual (tudo no mesmo chat, ID fixo). Detecção via `chat.type == "supergroup"` + presença de `is_forum=True` no chat info.

**Rationale:** Não quebra DMs nem grupos normais. Adoção gradual sem migração forçada.

### D5: Propagação de thread_id via MessageContext

Novo dataclass `MessageContext` encapsula `chat_id`, `user_id`, `thread_id` e `demand_id`. Substitui o uso de `chat_id` solto passado entre daemon → engine → callbacks. Todos os métodos de envio do bus recebem `thread_id` opcional.

```python
@dataclass
class MessageContext:
    chat_id: str
    user_id: str
    thread_id: int | None = None
    demand_id: str | None = None
```

**Alternativas consideradas:**
- *Adicionar thread_id como parâmetro em cada método* — funciona mas polui assinaturas. Descartado: MessageContext é mais extensível (futuro: reply_to_message_id, etc).
- *Thread-local / contextvars* — implícito, difícil de testar. Descartado: explícito é melhor.

**Rationale:** Padrão Context Object. Um objeto atravessa a stack sem acoplar camadas a detalhes específicos do Telegram.

### D6: Criação de tópico no momento da delegação

Quando o Squad Lead chama `start_agent(name, task)` e o modo fórum está ativo, o daemon:
1. Gera `demand_id` via `_generate_demand_id(task)`
2. Cria Forum Topic via `bus.create_thread(chat_id, título)`
3. Persiste mapeamento `thread_id ↔ demand_id`
4. Envia mensagem inicial no tópico ("Demanda criada. Pipeline iniciado.")
5. Inicia o agente com o `demand_id` e `thread_id` associados

**Rationale:** O tópico nasce junto com a demanda, não antes nem depois. Garante que toda mensagem da demanda já vai pro tópico certo desde o início.

## Risks / Trade-offs

- **[Grupo-fórum obrigatório]** → Usuários precisam converter o grupo para modo fórum no Telegram. Mitigação: documentação clara + fallback para modo flat.
- **[Limite de tópicos]** → Telegram permite até ~1000 tópicos por grupo. Mitigação: suficiente para uso normal; no futuro, fechar tópicos de demandas concluídas.
- **[Latência ao criar tópico]** → Uma chamada extra à API do Telegram por demanda nova (~100-300ms). Mitigação: aceitável, acontece uma vez por demanda.
- **[Complexidade de testes]** → Forum Topics requerem supergrupo real para testes E2E. Mitigação: mock do bot API nos testes unitários; thread_id é apenas um int propagado.
- **[Breaking change em callbacks]** → Engine e agentes precisam propagar MessageContext. Mitigação: thread_id é opcional (None = comportamento atual), mudança aditiva.
