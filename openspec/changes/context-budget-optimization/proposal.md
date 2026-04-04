## Why

O overhead de orquestração consome ~167K tokens por demanda (3 agentes, 5 ciclos do Squad Lead), sendo ~40% duplicação e contexto irrelevante. Cada invocação do Squad Lead injeta 25-110K tokens de contexto, com journal/demand_state/conversation duplicando informação de estado, system instructions injetadas 2x, e mecanismos de aprendizagem (lessons, daily_notes, graph) carregados upfront mesmo quando irrelevantes. Agentes recebem AGENTS.md duplicado e re-buscam lessons/graph já consultados pelo Squad Lead. A meta é reduzir o consumo para ~48K tokens/demanda (~71% de economia) sem degradar a qualidade das respostas.

## What Changes

- **Context Budget com tiers**: Novo componente `ContextBudget` que distribui tokens por prioridade (Tier 1 crítico/fixo, Tier 2 relevante/encolhível, Tier 3 complementar/descartável) com estimativa de tokens e shrink progressivo
- **Prompt caching via API Anthropic**: Marcar system prompt e tool definitions com `cache_control: {"type": "ephemeral"}` para reutilizar tokens estáticos entre chamadas (~40-50% economia nos tokens fixos)
- **Deduplicação de contexto**: Unificar journal/demand_state/conversation em fonte única de estado; remover injeção dupla de system instructions e AGENTS.md
- **Memória on-demand (híbrida)**: Substituir injeção upfront de lessons/daily_notes/graph por catálogo mínimo (~300 tokens) + tools `query_lessons()`, `query_journal()`, `query_daily_notes()` para consulta sob demanda
- **Sessão quente de agente**: Preservar sessão do agente entre delegações da mesma demanda, reutilizando contexto já carregado em vez de reconstruir do zero

## Capabilities

### New Capabilities
- `context-budget`: Gerenciamento de orçamento de tokens com distribuição por tiers, estimativa de tokens e shrink progressivo por componente
- `prompt-caching`: Configuração de cache breakpoints na API Anthropic para reutilizar tokens estáticos entre chamadas
- `on-demand-memory`: Tools MCP para consulta sob demanda de lessons, journal e daily notes, com catálogo mínimo injetado no prompt

### Modified Capabilities
- `orchestrator`: Deduplicação de contexto (journal/demand/conversation unificados), remoção de system instructions duplicadas, integração com ContextBudget na montagem de prompts
- `ai-agent-adapter`: Remoção de AGENTS.md/lessons/graph duplicados no prompt do agente, suporte a sessão quente entre delegações, integração com prompt caching

## Impact

- **Arquivos principais**: `engine.py`, `agent_runner.py`, `prompt_builder.py` (ambos), `conversation.py`, `context.py`, `lessons.py`, `journal.py`, `daily_notes.py`, `mcp_tools_server.py`
- **Novo arquivo**: `ai_squad/orchestrator/context_budget.py`
- **Adapters**: `claude_agent_sdk.py`, `copilot_adapter.py`, `agno_adapter.py` (prompt caching + sessão quente)
- **Dependências**: `tiktoken` (opcional, para contagem precisa de tokens)
- **APIs**: 3 novas MCP tools (`query_lessons`, `query_journal`, `query_daily_notes`)
- **Compatibilidade**: Sem breaking changes — comportamento externo idêntico, economia interna de tokens
