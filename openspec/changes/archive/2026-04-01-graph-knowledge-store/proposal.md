## Why

O sistema atual de aprendizado (LessonsStore) guarda fatos isolados — "problema X, solução Y" — sem conectar relações entre conceitos. Quando um bug é causado por um padrão que só acontece em determinado módulo, o sistema não consegue navegar essa cadeia. O resultado: agentes repetem investigações e não aproveitam conhecimento relacional acumulado entre demandas. Um grafo de conhecimento leve, usando SQLite (já presente no projeto) com extração via LLM, resolve isso sem adicionar dependências externas.

## What Changes

- Novo módulo `src/orchestrator/graph.py` com `GraphStore` — grafo de conhecimento em SQLite usando recursive CTEs para traversal
- 3 tabelas SQLite: `entities`, `relations`, `entities_fts` (FTS5 para busca rápida por nome/descrição)
- Extração de entidades e relações via callback LLM (mesmo padrão do `ConversationStore.set_summarize_callback`)
- Ingestão automática em 4 pontos: conclusão de demanda, lição registrada, resultado de agente, quality gate rejeitado
- Consulta do grafo injetada no prompt do Squad Lead e dos agentes via `format_for_prompt()`
- Nova MCP tool `query_knowledge_graph` para consulta explícita pelo Squad Lead
- Reforço automático de relações: relações vistas múltiplas vezes ganham peso maior
- Pruning automático: entidades/relações antigas e pouco usadas são removidas

## Capabilities

### New Capabilities
- `graph-knowledge`: Grafo de conhecimento relacional com entidades, relações, extração via LLM, traversal via recursive CTE, reforço de peso e pruning automático

### Modified Capabilities
- `orchestrator`: Integração do GraphStore nos pontos de ingestão (conclusão de demanda, lição, resultado de agente) e consulta (montagem de prompt)

## Impact

- **Código novo**: `src/orchestrator/graph.py` (~250-350 linhas)
- **Código modificado**: `engine.py` (~20 linhas — init + callbacks), `agent_runner.py` (injeção no prompt), `prompt_builder.py` (nova função `get_graph_context`), `mcp_tools_server.py` (nova tool)
- **Dependências**: nenhuma nova (SQLite stdlib + JSON)
- **Storage**: novo arquivo `graph.db` no state_dir de cada time
- **Custo LLM**: 1 call "fast" (haiku/flash) por ingestão — async, não bloqueia fluxo principal
