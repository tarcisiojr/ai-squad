## MODIFIED Requirements

### Requirement: Injeção de contexto do grafo no prompt
O orquestrador SHALL disponibilizar contexto do GraphStore via MCP tool `query_knowledge_graph(query)` em vez de injeção automática no prompt. O catálogo de memória SHALL indicar a disponibilidade do grafo. Injeção automática no prompt do Squad Lead e agentes SHALL ser removida.

#### Scenario: Prompt do Squad Lead sem injeção automática de grafo
- **WHEN** `run_squad_lead()` monta o prompt para uma demanda
- **THEN** o prompt NÃO inclui seção automática de contexto do grafo, mas o catálogo indica disponibilidade via tool

#### Scenario: Squad Lead consulta grafo sob demanda
- **WHEN** o Squad Lead precisa de contexto semântico e invoca `query_knowledge_graph("autenticação")`
- **THEN** a tool retorna entidades e relações relevantes formatadas

#### Scenario: Prompt do agente sem injeção automática de grafo
- **WHEN** `agent_runner` monta o prompt para um agente
- **THEN** o prompt NÃO inclui seção automática de contexto do grafo

#### Scenario: Grafo consultável por agentes
- **WHEN** um agente precisa de contexto e invoca `query_knowledge_graph("tema")`
- **THEN** a tool retorna resultado formatado do traversal

## ADDED Requirements

### Requirement: Deduplicação de fontes de estado
O orquestrador SHALL montar uma seção unificada "Estado da Demanda" que combina: status atual (pipeline_state), últimas mensagens relevantes (conversation sumarizada), e decisões-chave (journal comprimido). As injeções separadas de journal_summary e demand_state SHALL ser removidas.

#### Scenario: Seção unificada substitui fontes duplicadas
- **WHEN** o engine monta contexto para o Squad Lead com demanda ativa
- **THEN** o prompt contém uma única seção "Estado da Demanda" e NÃO contém seções separadas de journal_summary ou demand_state

#### Scenario: Seção unificada inclui decisões do journal
- **WHEN** o journal tem 5 decisões registradas para a demanda ativa
- **THEN** a seção "Estado da Demanda" inclui as decisões como bullet points compactos

### Requirement: System instructions sem duplicação
O orquestrador SHALL injetar system instructions (AGENTS.md, role) em um único ponto do prompt. A injeção dupla via engine + adapter prompt_builder SHALL ser eliminada.

#### Scenario: System instructions aparecem uma vez
- **WHEN** o prompt completo é montado para o Squad Lead
- **THEN** as system instructions aparecem exatamente 1 vez no prompt final

### Requirement: Integração com ContextBudget
O orquestrador SHALL usar `ContextBudget` para montar prompts do Squad Lead e dos agentes. Cada componente de contexto SHALL ser adicionado ao tier apropriado. O prompt final SHALL respeitar o budget total.

#### Scenario: Squad Lead usa ContextBudget
- **WHEN** o engine monta prompt para o Squad Lead
- **THEN** todos os componentes são adicionados via `ContextBudget.add()` com tier e shrink_fn apropriados e o prompt é montado via `ContextBudget.build()`

#### Scenario: Agente usa ContextBudget
- **WHEN** o agent_runner monta prompt para um agente
- **THEN** os componentes são adicionados via `ContextBudget` com budget de 4000 tokens
