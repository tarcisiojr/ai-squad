## ADDED Requirements

### Requirement: Sessão quente entre delegações
Os adapters SHALL preservar sessão de agentes entre delegações da mesma demanda. A sessão SHALL ser identificada por `agent_name--demand_id`. Delegações subsequentes ao mesmo agente na mesma demanda SHALL reutilizar o contexto já carregado, enviando apenas a nova task.

#### Scenario: Primeira delegação cria sessão
- **WHEN** o agent_runner delega tarefa ao "dev-backend" na demanda #42 pela primeira vez
- **THEN** o adapter cria sessão "dev-backend--42" com contexto completo

#### Scenario: Segunda delegação reutiliza sessão
- **WHEN** o agent_runner delega nova tarefa ao "dev-backend" na demanda #42 e a sessão existe e não expirou
- **THEN** o adapter envia apenas a nova task sem reconstruir o contexto base

#### Scenario: Sessão expirada recria contexto
- **WHEN** a sessão "dev-backend--42" tem TTL expirado (>300s de inatividade)
- **THEN** o adapter descarta a sessão e cria uma nova com contexto completo

### Requirement: Remoção de contexto duplicado no prompt do agente
Os adapters SHALL NOT injetar AGENTS.md quando o mesmo já está presente no workspace_context. Lessons e graph_ctx SHALL NOT ser re-buscados quando já consultados pelo Squad Lead para a mesma demanda.

#### Scenario: AGENTS.md não duplicado
- **WHEN** o prompt do agente já contém AGENTS.md via workspace_context
- **THEN** o adapter NÃO adiciona AGENTS.md novamente via system_instructions

#### Scenario: Lessons não re-buscadas
- **WHEN** o Squad Lead já consultou lessons para a demanda atual
- **THEN** o agent_runner NÃO executa nova busca FTS5 de lessons para o agente

### Requirement: Prompt caching no Claude adapter
O Claude adapter SHALL configurar `cache_control` breakpoints no system prompt e tool definitions para chamadas à API Anthropic. Outros adapters SHALL ignorar esta funcionalidade.

#### Scenario: System prompt com cache_control
- **WHEN** o Claude adapter envia prompt à API Anthropic
- **THEN** o bloco de system prompt inclui `cache_control: {"type": "ephemeral"}`

#### Scenario: Adapter Agno ignora caching
- **WHEN** o Agno adapter envia prompt ao Google Gemini
- **THEN** nenhum campo de cache_control é adicionado
