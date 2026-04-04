## Context

O sistema de orquestração monta prompts concatenando ~11 componentes de contexto sem visão do tamanho total. Isso resulta em ~25-110K tokens por invocação do Squad Lead, com duplicações entre journal/demand_state/conversation, system instructions injetadas 2x, e mecanismos de memória (lessons, daily_notes, graph) carregados sempre — mesmo quando irrelevantes. Agentes recebem AGENTS.md duplicado e re-buscam lessons/graph já consultados pelo Squad Lead. Uma demanda típica com 3 agentes consome ~167K tokens só em overhead de orquestração.

Estado atual dos limites: cada componente tem teto próprio (MAX_CONTEXT_LESSONS=10, MAX_CONTEXT_MESSAGES=20, MAX_CLAUDE_MD_CHARS=6000, etc.) mas não existe controle do total agregado nem priorização quando o conjunto não cabe. Não há contagem de tokens nem awareness do context window do modelo.

## Goals / Non-Goals

**Goals:**
- Reduzir overhead de orquestração de ~167K para ~48K tokens/demanda (~71% economia)
- Implementar distribuição de tokens por prioridade (tiers) com shrink progressivo
- Eliminar duplicações de contexto (journal/demand/conversation, system instructions, AGENTS.md)
- Converter memória de injeção upfront para modelo híbrido catálogo + on-demand
- Habilitar prompt caching na API Anthropic para tokens estáticos
- Preservar sessão de agentes entre delegações da mesma demanda

**Non-Goals:**
- Mudar comportamento externo do sistema (respostas ao usuário, fluxo de pipeline)
- Implementar contagem exata de tokens (estimativa por caracteres é suficiente)
- Adicionar dependência obrigatória de tiktoken (opcional para calibração)
- Alterar a interface ABC dos adapters (mudanças são internas)
- Otimizar o conteúdo dos prompts em si (foco é na estrutura/quantidade, não na redação)

## Decisions

### D1: Estimador de tokens por divisão de caracteres (não tiktoken)

**Escolha:** `estimate_tokens(text) → len(text) // 3` para português/código misto.

**Alternativas:**
- tiktoken: preciso mas adiciona dependência de ~3MB e é específico para modelos OpenAI
- API usage.input_tokens: preciso mas só disponível após a chamada (tarde demais para budget)
- Contagem de palavras: impreciso para código

**Rationale:** Precisão de ~85% é suficiente para budget allocation. O budget já tem margem de segurança. Opcionalmente, o divisor pode ser calibrado via `usage.input_tokens` das respostas reais.

### D2: ContextBudget como classe standalone injetada no engine

**Escolha:** Nova classe `ContextBudget` em `ai_squad/orchestrator/context_budget.py` que recebe seções por tier e monta o prompt final respeitando o budget.

**Alternativas:**
- Modificar engine.py inline: menor mudança mas acopla lógica de budget ao orquestrador
- Decorator/middleware no adapter: tarde demais, contexto já foi montado
- Condenser plugável (estilo OpenHands): mais flexível mas over-engineering para nosso caso

**Rationale:** Classe standalone permite testes unitários isolados, reutilização entre Squad Lead e agentes, e introdução incremental sem reescrever o engine.

**Interface:**
```python
class ContextBudget:
    def __init__(self, total_budget: int = 8000):
        ...
    def estimate_tokens(self, text: str) -> int:
        ...
    def add(self, tier: int, name: str, content: str,
            shrink_fn: Callable[[str, int], str] | None = None) -> None:
        ...
    def build(self) -> str:
        ...
    def usage_report(self) -> dict[str, int]:
        ...
```

### D3: Três tiers com budget fixo + flex + descartável

**Escolha:**
- **Tier 1 (crítico, ~3K tok):** instructions, task, pipeline_state, running_status, metadata — nunca trunca
- **Tier 2 (relevante, ~3K tok flex):** conversation, demand_state, workspace rules, catálogo de memória — encolhe por prioridade inversa
- **Tier 3 (complementar, ~2K tok):** daily_notes, graph_ctx, knowledge_ctx, tree/README — descartado se sem budget

**Alternativas:**
- 2 tiers (fixo/descartável): perde a capacidade de shrink gradual
- Budget proporcional (% por componente): não reflete que alguns componentes são mais críticos
- Sem tiers, só cortar por tamanho: perde semântica

**Rationale:** 3 tiers equilibram simplicidade e controle. O shrink do Tier 2 usa funções específicas por componente (sumarizar conversa, reduzir lessons de 10→3, comprimir workspace para headers).

### D4: Budget diferenciado por papel

**Escolha:**
| Papel | Budget | Justificativa |
|-------|--------|---------------|
| Squad Lead | 8K tok | Precisa do contexto completo para coordenar |
| Agent (tarefa) | 4K tok | Precisa de workspace + tarefa, tem tools para buscar mais |
| Agent (review) | 6K tok | Precisa do artefato anterior + quality gate |

**Rationale:** Agentes com acesso a tools (filesystem, git) não precisam de contexto estático extenso. Podem buscar on-demand o que falta.

### D5: Prompt caching via cache_control na API Anthropic

**Escolha:** Marcar system prompt e tool definitions com `cache_control: {"type": "ephemeral"}` nos adapters Claude.

**Alternativas:**
- Sem caching: funciona mas paga 100% em tokens estáticos repetidos
- Cache em disco (estilo Aider): não se aplica à API Anthropic

**Rationale:** Economia de ~90% nos tokens estáticos (system prompt + tools) entre chamadas dentro de 5 minutos. Implementação mínima (1 campo extra na mensagem). Copilot e Agno não suportam — aplicar apenas ao Claude adapter.

### D6: Deduplicação por fonte única de estado

**Escolha:** Unificar journal + demand_state + conversation em uma única seção "Estado da Demanda" montada pelo engine, eliminando 3 fontes redundantes.

**Composição:**
- Status atual (do pipeline_state)
- Últimas N mensagens relevantes (do conversation, já sumarizado)
- Decisões-chave (do journal, comprimido para bullet points)

**Alternativas:**
- Manter separados com dedup automática: complexo e frágil
- Só remover journal (menor impacto): perde a oportunidade de unificação

**Rationale:** As 3 fontes contêm informação sobreposta formatada diferentemente. Uma fonte unificada é mais clara para o LLM (menos conflito entre representações) e mais econômica.

### D7: Memória híbrida — catálogo + on-demand

**Escolha:** Injetar catálogo mínimo (~300 tok) listando temas disponíveis + 3 novas MCP tools para consulta sob demanda.

**Catálogo injetado:**
```
Lições disponíveis (N total): [lista de temas]
Journal ativo: demandas #X, #Y
Notas: últimos 3 dias disponíveis.
Use query_lessons/query_journal/query_daily_notes para detalhes.
```

**Tools:**
- `query_lessons(tema: str, limit: int = 5) → str` — FTS5 search
- `query_journal(demand_id: str | None) → str` — decisões de uma demanda
- `query_daily_notes(days: int = 3) → str` — notas recentes

**Alternativas:**
- Full on-demand (sem catálogo): risco de "não saber o que não sabe"
- Manter injeção upfront: desperdiça ~7K tokens/chamada
- Smart injection (injetar só se relevante): requer classificador, complexo

**Rationale:** O catálogo resolve o problema "you don't know what you don't know" com custo mínimo. O Squad Lead vê os temas e decide se precisa consultar. Economia de ~6.7K tokens/chamada quando não consulta.

### D8: Sessão quente de agente com TTL

**Escolha:** `AgentSession` preserva contexto entre delegações da mesma demanda ao mesmo agente.

```python
@dataclass
class AgentSession:
    session_id: str          # "agent_name--demand_id"
    created_at: float
    context_loaded: bool     # True se contexto base já foi enviado
    turn_count: int
    ttl: int = 300           # expira em 5 min de inatividade
```

**Fluxo:**
1. Primeira delegação: monta contexto completo (4K tok)
2. Delegações seguintes: envia apenas a nova task (~500 tok)
3. Se TTL expirou: recria sessão do zero

**Alternativas:**
- Sem sessão (hoje): reconstrução completa a cada delegação
- Sessão permanente: risco de contexto stale e memory leak
- Condenser na sessão (estilo OpenHands): complexidade extra desnecessária inicialmente

**Rationale:** O Copilot adapter já usa sessions por agent_name--demand_id. Generalizar para todos os adapters. TTL de 5 min cobre a maioria das demandas sem acumular memória.

## Risks / Trade-offs

**[Degradação por contexto insuficiente]** → Mitigação: Tier 1 nunca é cortado. Tier 2 encolhe gradualmente (não trunca). Catálogo garante awareness do que existe. Agentes têm tools para buscar mais. Monitorar qualidade nas primeiras semanas via journal.

**[Estimativa de tokens imprecisa]** → Mitigação: Margem de 15% no budget. Calibrar divisor via usage.input_tokens real. Errar pra mais é preferível a errar pra menos.

**[Squad Lead não consulta tools on-demand]** → Mitigação: Catálogo explícito com instrução de uso. Testar se o LLM usa as tools consistentemente antes de remover injeção upfront. Fallback: re-injetar se taxa de consulta < 50%.

**[Sessão quente com contexto stale]** → Mitigação: TTL curto (5 min). Reset automático em nova demanda. Agente pode invalidar sessão se detectar inconsistência.

**[Prompt caching não disponível em todos os providers]** → Mitigação: Implementar apenas no Claude adapter. Copilot e Agno ignoram. Abstrair via flag no adapter.

**[Complexidade incremental]** → Mitigação: Implementar em 5 fases ordenadas por ROI/risco. Cada fase é independente e pode ser revertida. Fase 1 (dedup + caching) não requer ContextBudget.

## Migration Plan

**Fase 1 — Zero risco (dedup + caching):**
1. Remover injeção dupla de system instructions (adapter prompt_builder)
2. Remover AGENTS.md duplicado no contexto de agentes (agent_runner)
3. Unificar journal/demand_state em seção única no engine
4. Adicionar cache_control no Claude adapter
5. Validar: testes existentes devem passar sem alteração

**Fase 2 — Baixo risco (memória on-demand):**
1. Implementar 3 MCP tools (query_lessons, query_journal, query_daily_notes)
2. Substituir injeção upfront por catálogo mínimo
3. Testar: Squad Lead usa tools corretamente? Monitorar por 1 semana

**Fase 3 — Médio risco (context budget):**
1. Criar ContextBudget com tiers e estimador
2. Integrar no engine.py (Squad Lead)
3. Integrar no agent_runner.py (agentes)
4. Implementar shrink_fn por componente

**Fase 4 — Médio risco (sessão quente):**
1. Criar AgentSession com TTL
2. Integrar no agent_runner.py
3. Adaptar Claude/Copilot/Agno adapters

**Rollback:** Cada fase é revertível via git revert. ContextBudget pode ser bypassado com `budget=float('inf')`. Memória on-demand pode fallback para injeção upfront via flag.

## Open Questions

1. **Qual o budget ideal por papel?** Os valores 8K/4K/6K são estimativas baseadas na análise. Precisam ser calibrados com demandas reais.
2. **O Squad Lead vai usar tools de memória consistentemente?** Precisa de teste empírico. Se não usar, o catálogo pode precisar ser mais detalhado ou a injeção parcial mantida.
3. **O TTL de 5 min para sessão quente é adequado?** Depende do tempo médio entre delegações. Se demandas demoram mais, pode precisar aumentar.
4. **Prompt caching funciona com o Claude Agent SDK?** Verificar se o SDK expõe o campo cache_control ou se precisa de chamada direta à API.
