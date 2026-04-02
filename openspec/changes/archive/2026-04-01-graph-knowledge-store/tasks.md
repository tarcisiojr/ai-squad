## 1. GraphStore core (graph.py)

- [x] 1.1 Criar `src/orchestrator/graph.py` com classe `GraphStore`: init_db com tabelas `entities`, `relations`, `entities_fts` (FTS5), lazy connection (mesmo padrão LessonsStore)
- [x] 1.2 Implementar `add_entity(name, type, description, demand_id)` com deduplicação por `(name_normalized, type)` e incremento de mention_count
- [x] 1.3 Implementar `add_relation(from_name, from_type, to_name, to_type, rel_type, evidence, demand_id)` com reforço de weight para relações existentes
- [x] 1.4 Implementar `traverse(entity_name, depth=3)` via recursive CTE retornando entidades e relações conectadas
- [x] 1.5 Implementar `query(text, limit=10)` combinando FTS5 match em entities_fts + expansão por traversal
- [x] 1.6 Implementar `format_for_prompt(query)` com formatação Markdown hierárquica (MAX_CONTEXT_RESULTS=8)
- [x] 1.7 Implementar `reinforce(from_name, to_name, delta)` para ajuste manual de peso
- [x] 1.8 Implementar `prune()` com remoção de entidades (mention_count=1, age > 30d) e relações (weight <= 0), respeitando MAX_ENTITIES=500 e MAX_RELATIONS=2000
- [x] 1.9 Implementar `stats()` retornando contagem de entidades, relações e top entidades por mention_count

## 2. Extração via LLM

- [x] 2.1 Implementar `set_extract_callback(fn)` e prompt de extração com tipos fechados (entidades + relações) e lista de entidades existentes para deduplicação
- [x] 2.2 Implementar `ingest(text, demand_id)` como async fire-and-forget: chama callback, parseia JSON, valida tipos, persiste entidades e relações. Throttle de 10s por demand_id
- [x] 2.3 Implementar validação estrita do JSON retornado: schema de entidades (name, type, description) e relações (from, to, type, evidence) com tipos permitidos

## 3. Integração com engine

- [x] 3.1 Instanciar `GraphStore` no `OrchestrationEngine.__init__` e registrar callback `set_extract_callback(self._extract_via_llm)`
- [x] 3.2 Chamar `graph.ingest()` no `_handle_learn_lesson` (após registrar lição)
- [x] 3.3 Chamar `graph.ingest()` no `_trigger_squad_lead_for_agent` (conclusão de agente com resultado)
- [x] 3.4 Chamar `graph.ingest()` na conclusão de demanda (journal summary)
- [x] 3.5 Adicionar `get_graph_context()` no `prompt_builder.py` e injetar no prompt do Squad Lead em `run_squad_lead()`

## 4. Integração com agent_runner e MCP

- [x] 4.1 Injetar contexto do grafo no prompt dos agentes em background via `agent_runner._build_prompt()`
- [x] 4.2 Registrar MCP tool `query_knowledge_graph(query)` no `mcp_tools_server.py` com callback para `graph.query()` formatado
- [x] 4.3 Registrar callback no engine: `self._adapter.set_query_graph_callback(self._handle_query_graph)`

## 5. Testes

- [x] 5.1 Testes unitários do GraphStore: add_entity, add_relation, deduplicação, traverse, query, prune, format_for_prompt
- [x] 5.2 Testes da extração: mock do callback LLM, validação de JSON, throttle, falha tolerante
- [x] 5.3 Testes de integração: ingestão via engine callbacks, injeção no prompt, MCP tool
