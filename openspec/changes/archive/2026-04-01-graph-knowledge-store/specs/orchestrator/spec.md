## ADDED Requirements

### Requirement: Integração do GraphStore nos pontos de ingestão
O orquestrador SHALL invocar `GraphStore.ingest()` nos seguintes eventos: conclusão de demanda (journal summary + resultado), lição registrada via learn_lesson, resultado de agente em background, e quality gate rejeitado. A ingestão SHALL ser fire-and-forget e tolerante a falha.

#### Scenario: Ingestão na conclusão de demanda
- **WHEN** uma demanda é concluída (pipeline completa ou fechamento manual)
- **THEN** o orquestrador invoca `graph.ingest()` com o resumo do journal e resultado final

#### Scenario: Ingestão ao registrar lição
- **WHEN** o callback `_handle_learn_lesson` é executado
- **THEN** o orquestrador invoca `graph.ingest()` com category, problem e solution formatados

#### Scenario: Ingestão ao concluir agente
- **WHEN** um agente em background conclui com resultado
- **THEN** o orquestrador invoca `graph.ingest()` com agent_name, task e resultado

#### Scenario: Falha na ingestão não afeta fluxo
- **WHEN** `graph.ingest()` falha com exceção
- **THEN** o orquestrador loga o erro e continua normalmente

### Requirement: Injeção de contexto do grafo no prompt
O orquestrador SHALL injetar contexto do GraphStore no prompt do Squad Lead e dos agentes via `graph.format_for_prompt(query)`. O contexto SHALL ser adicionado como seção separada no prompt.

#### Scenario: Prompt do Squad Lead inclui contexto do grafo
- **WHEN** `run_squad_lead()` monta o prompt para uma demanda
- **THEN** o prompt inclui seção "Conhecimento relacionado (grafo)" com entidades e relações relevantes ao texto da demanda

#### Scenario: Prompt do agente inclui contexto do grafo
- **WHEN** `agent_runner` monta o prompt para um agente com tarefa específica
- **THEN** o prompt inclui contexto do grafo relevante à tarefa do agente

#### Scenario: Grafo vazio não polui prompt
- **WHEN** o GraphStore não tem resultados para a query
- **THEN** nenhuma seção de grafo é adicionada ao prompt

### Requirement: MCP tool query_knowledge_graph
O orquestrador SHALL expor uma MCP tool `query_knowledge_graph(query)` que permite ao Squad Lead consultar o grafo explicitamente. A tool SHALL retornar o resultado formatado do traversal.

#### Scenario: Squad Lead consulta grafo explicitamente
- **WHEN** o Squad Lead invoca `query_knowledge_graph("autenticação")`
- **THEN** a tool retorna entidades e relações conectadas ao termo, formatadas para leitura

#### Scenario: Consulta sem resultados
- **WHEN** o Squad Lead invoca `query_knowledge_graph("termo inexistente")`
- **THEN** a tool retorna mensagem indicando que não há conhecimento sobre o termo
