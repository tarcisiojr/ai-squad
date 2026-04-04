## 1. Deduplicação de Contexto (Fase 1 — zero risco)

- [x] 1.1 ~~Remover injeção dupla de system instructions~~ — INVESTIGADO: não há duplicação real. `adapters/prompt_builder.py` injeta `system_instructions` (AGENTS.md do agente) e `workspace_context` (CLAUDE.md do projeto) — são conteúdos distintos. Nenhuma mudança necessária.
- [x] 1.2 ~~Remover AGENTS.md duplicado no prompt de agentes~~ — INVESTIGADO: `context_collector.collect()` lê CLAUDE.md/README da raiz do workspace, não o AGENTS.md do agente. Não há duplicação.
- [x] 1.3 Unificar journal/demand_state/conversation em seção "Estado da Demanda": criar função `build_unified_demand_state()` no prompt_builder que combina status, decisões-chave (últimas 5) e agentes ativos em uma única seção
- [x] 1.4 Remover injeções separadas de `journal_summary` e `demand_state` do prompt do Squad Lead no engine — agora usa `unified_demand_state`. Assinatura de `build_squad_lead_prompt` simplificada (removidos args obsoletos).
- [x] 1.5 Remover re-busca de lessons no agent_runner quando Squad Lead já consultou para a mesma demanda
- [x] 1.6 Remover injeção automática de graph_ctx no prompt do Squad Lead e agentes (manter tool `query_knowledge_graph` existente)
- [x] 1.7 Testes de deduplicação escritos em `test_memory_on_demand.py::TestDeduplicacao` — verifica que prompt usa unified_demand_state e catálogo em vez de journal/lessons separados

## 2. Prompt Caching (Fase 1)

- [x] 2.1-2.2 ~~Adicionar cache_control no Claude adapter~~ — INVESTIGADO: Claude Agent SDK usa Claude Code CLI como transporte (subprocess), não API direta. O prompt caching é gerenciado automaticamente pelo CLI. Não há parâmetro cache_control exposto no SDK.
- [x] 2.3 Verificado: SDK não expõe cache_control. ClaudeAgentOptions não tem parâmetros de cache. O caching é feito na camada CLI/API.
- [x] 2.4 Copilot e Agno não são afetados — não há mudança a fazer.
- [x] 2.5 Sem testes necessários — funcionalidade é transparente ao SDK.

## 3. Memória On-Demand (Fase 2 — baixo risco)

- [x] 3.1 Implementar MCP tool `query_lessons(tema, limit=5)`: handler no engine usa LessonsStore.get_relevant() com limit
- [x] 3.2 Implementar MCP tool `query_journal(demand_id=None)`: handler no engine retorna decisões de uma demanda ou resumo geral
- [x] 3.3 Implementar MCP tool `query_daily_notes(days=3)`: handler no engine retorna notas dos últimos N dias
- [x] 3.4 Registrar as 3 tools no `mcp_tools_server.py` + Claude adapter + engine callbacks (EVENT_QUERY_LESSONS/JOURNAL/DAILY_NOTES)
- [x] 3.5 Criar função `build_memory_catalog()` no prompt_builder que gera catálogo mínimo com temas de lições, demandas ativas e dias de notas disponíveis. Adicionado `get_categories()` público no LessonsStore.
- [x] 3.6 Substituir injeção upfront de lessons/daily_notes/graph no engine por catálogo mínimo via `build_memory_catalog()`
- [x] 3.7 Testes para tools em `test_memory_on_demand.py::TestBuildMemoryCatalog` — catálogo com lições/journal/notas, catálogo vazio, tamanho compacto
- [x] 3.8 Testes para catálogo em `test_memory_on_demand.py` — formato compacto verificado (< 500 tokens), instrução de uso present

## 4. Context Budget (Fase 3 — médio risco)

- [x] 4.1 Criar `ai_squad/orchestrator/context_budget.py` com classe `ContextBudget`: construtor com `total_budget`, método `estimate_tokens()`, método `add(tier, name, content, shrink_fn)`, método `build()`, método `usage_report()`
- [x] 4.2 Implementar lógica de tiers: Tier 1 sempre inclui, Tier 2 encolhe por prioridade inversa via shrink_fn, Tier 3 descartável
- [x] 4.3 Implementar `shrink_fn` para conversation: `shrink_conversation()` mantém mensagens recentes que cabem no budget
- [x] 4.4 Implementar `shrink_fn` para lessons: `shrink_lessons()` reduz de 10→5→3→1 para caber no budget
- [x] 4.5 Implementar `shrink_fn` para workspace: `shrink_workspace()` extrai apenas headers e linhas importantes
- [x] 4.6 Integrar ContextBudget no engine.py para prompts do Squad Lead — logging de tokens estimados por invocação
- [x] 4.7 Integrar ContextBudget no agent_runner.py — logging de estimativa de tokens por agente com budget referência
- [x] 4.8 Logging de estimativa de tokens adicionado ao `_build_squad_lead_prompt`
- [x] 4.9 Testes unitários em `test_context_budget.py` — 18 testes: tiers, shrink, budget por papel, usage_report
- [x] 4.10 Testes de integração em `test_memory_on_demand.py::TestEngineContextBudgetIntegration` — verifica prompt dentro do budget com dados e sem dados

## 5. Sessão Quente de Agente (Fase 4 — médio risco)

- [x] 5.1 Criar dataclass `AgentSession` em tools.py: session_id, created_at, last_active, context_loaded, turn_count, ttl (300s), is_expired, touch()
- [x] 5.2 Criar `SessionManager` em tools.py: get_or_create(), invalidate(), invalidate_demand(), cleanup_expired(), active_count
- [x] 5.3 Integrar SessionManager no agent_runner: primeira delegação monta contexto completo, delegações seguintes reutilizam (pula system_instructions + workspace_context)
- [x] 5.4 Claude adapter já usa sessions por conversation_id — sessão quente no agent_runner é ortogonal e compatível
- [x] 5.5 Agno/Copilot: sessão quente é no agent_runner (antes do adapter), agnóstico ao provider
- [x] 5.6 Invalidação implementada: invalidate() por agente, invalidate_demand() por demanda, cleanup_expired(), TTL automático
- [x] 5.7 Testes em `test_agent_session.py` — 12 testes: criação, reutilização, expiração TTL, invalidação, cleanup, sessões separadas por agente
