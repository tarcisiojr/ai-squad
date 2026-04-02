# orchestrator

## Purpose

Motor de orquestração que controla o ciclo de vida de demandas através de máquina de estados, despacho de agentes e roteamento de decisões humanas — totalmente desacoplado de providers concretos.

## Requirements

### Requirement: Máquina de estados do ciclo de vida
O orquestrador SHALL gerenciar o ciclo de vida de cada demanda através dos estados: `idle` → `po_working` → `awaiting_plan_approval` → `dev_working` → `awaiting_pr_approval` → `ci_running` → `qa_validating` → `done`. Transições inválidas SHALL ser rejeitadas com erro.

#### Scenario: Ciclo completo bem-sucedido
- **WHEN** uma nova demanda é recebida e todos os passos são aprovados
- **THEN** a demanda transiciona por todos os estados em ordem até `done`

#### Scenario: Transição inválida rejeitada
- **WHEN** uma tentativa de transição de `idle` para `dev_working` é feita
- **THEN** o sistema rejeita a transição e mantém o estado atual

### Requirement: Persistência de estado
O orquestrador SHALL persistir o estado de cada demanda em arquivo JSON. O estado SHALL sobreviver a reinicializações do sistema. O orquestrador SHALL executar cleanup de demandas expiradas no boot e no início de cada nova demanda.

#### Scenario: Recuperação após reinício
- **WHEN** o sistema reinicia com uma demanda em estado `dev_working`
- **THEN** o orquestrador carrega o estado do JSON e retoma a partir de `dev_working`

#### Scenario: Cleanup no boot do daemon
- **WHEN** o daemon inicia
- **THEN** o orquestrador executa `cleanup_expired()` antes de processar novas mensagens

#### Scenario: Cleanup ao iniciar nova demanda
- **WHEN** uma nova demanda é recebida pelo engine
- **THEN** o orquestrador executa `cleanup_expired()` antes de processar a demanda

### Requirement: Despacho de agentes via adapter
O orquestrador SHALL disparar agentes exclusivamente via `AIAgentAdapter` interface. O orquestrador SHALL NOT importar ou conhecer implementações concretas de IA.

#### Scenario: Despacho de agente PO
- **WHEN** uma demanda entra no estado `po_working`
- **THEN** o orquestrador invoca o adapter com o prompt e contexto do agente PO registrado no registry

### Requirement: Roteamento de decisões humanas
O orquestrador SHALL interceptar chamadas `ask()` dos agentes e rotear para o barramento via interface `MessageBus`. O orquestrador SHALL NOT interagir diretamente com canais de mensageria.

#### Scenario: Agente solicita aprovação de plano
- **WHEN** o agente PO emite um pedido de aprovação via `ask()`
- **THEN** o orquestrador envia a pergunta ao usuário via `MessageBus.send_approval_request` e retorna a resposta ao agente

### Requirement: Gerenciamento de worktrees git
O orquestrador SHALL criar e gerenciar worktrees git separadas para cada subagente, garantindo isolamento de código entre agentes trabalhando em paralelo.

#### Scenario: Dois agentes dev trabalhando em paralelo
- **WHEN** dois subagentes dev são disparados simultaneamente
- **THEN** cada um recebe uma worktree git independente e não interfere no trabalho do outro

### Requirement: Desacoplamento de providers
O orquestrador SHALL NOT ter conhecimento de qual provider de IA ou mensageria está em uso. Toda comunicação SHALL ser feita exclusivamente via interfaces ABC.

#### Scenario: Troca de provider não afeta orquestrador
- **WHEN** o provider de IA é trocado de Claude Code para Gemini no platform.yaml
- **THEN** o orquestrador continua funcionando sem nenhuma alteração em seu código

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
