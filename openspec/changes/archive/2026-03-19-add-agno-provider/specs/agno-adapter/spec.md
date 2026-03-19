# agno-adapter

## Purpose

Implementação do `AIAgentAdapter` usando o framework Agno, permitindo executar agentes com Gemini, OpenAI ou qualquer modelo suportado pelo Agno. Mantém paridade funcional com o `ClaudeAgentSDKAdapter`: MCP tools, sessions, delegação, model routing, retry com backoff e compressão de prompt.

## Requirements

### Requirement: Implementação da interface AIAgentAdapter
O `AgnoAdapter` SHALL implementar todos os métodos abstratos de `AIAgentAdapter`: `run(prompt, context) → str`, `ask(question) → str`, `status() → AgentStatus`, `on_human_needed(callback)`. O adapter SHALL ser selecionável via `ai_provider: agno` no config.yaml.

#### Scenario: Execução básica de agente
- **WHEN** o orquestrador chama `adapter.run(prompt, context)`
- **THEN** o adapter cria/retoma um agente Agno, executa com o prompt e retorna o resultado como string

#### Scenario: Seleção via config.yaml
- **WHEN** config.yaml tem `ai_provider: agno`
- **THEN** a factory instancia `AgnoAdapter` sem alteração em nenhum outro componente

### Requirement: Consumo das MCP tools do AI Squad
O adapter SHALL expor as 11 MCP tools existentes (report_progress, start_agent, get_running_agents, get_demand_state, get_pipeline_state, advance_step, skip_step, rerun_step, read_journal, send_image, learn_lesson) para o agente Agno via `MCPTools`. Os callbacks SHALL ser registrados via os mesmos `set_*_callback` da interface.

#### Scenario: Agente Agno chama start_agent
- **WHEN** o modelo Gemini decide chamar a tool `start_agent(agent_name, task_description)`
- **THEN** o callback `_start_agent_callback` é invocado e o resultado retornado ao modelo

#### Scenario: Todas as tools disponíveis
- **WHEN** o agente Agno é criado
- **THEN** todas as 11 MCP tools estão disponíveis para o modelo chamar

### Requirement: Gerenciamento de sessions
O adapter SHALL manter sessions por `conversation_id` (demand_id) para permitir retomada de contexto. SHALL usar `InMemorySessionService` ou `SqliteSessionService` do Agno para persistência.

#### Scenario: Retomada de sessão existente
- **WHEN** `run()` é chamado com um `demand_id` que já tem sessão ativa
- **THEN** o adapter retoma a sessão existente preservando histórico de conversa

#### Scenario: Nova sessão para nova demanda
- **WHEN** `run()` é chamado com um `demand_id` sem sessão
- **THEN** o adapter cria nova sessão e a registra para futuras retomadas

### Requirement: Model routing por tier
O adapter SHALL suportar model routing via campo `model_override` no contexto. SHALL mapear modelos Agno nativamente (Gemini, OpenAI, Claude) sem necessidade de LiteLLM para providers principais.

#### Scenario: Override de modelo para step rápido
- **WHEN** context contém `model_override: gemini-2.0-flash`
- **THEN** o adapter usa `Gemini(id="gemini-2.0-flash")` para essa execução e restaura o modelo original após

#### Scenario: Modelo padrão do config
- **WHEN** não há model_override no context
- **THEN** o adapter usa o modelo configurado em `ai_model` do config.yaml

### Requirement: Retry com backoff exponencial
O adapter SHALL implementar retry com backoff (2/4/8s) para erros transientes, idêntico ao `ClaudeAgentSDKAdapter`. SHALL tratar `context_length_exceeded` comprimindo o prompt. SHALL NOT fazer retry em timeout.

#### Scenario: Erro transiente com retry
- **WHEN** a execução falha com erro transiente (ex: rate limit)
- **THEN** o adapter retenta até 3 vezes com backoff exponencial (2s, 4s, 8s)

#### Scenario: Context length exceeded
- **WHEN** o modelo retorna erro de context length
- **THEN** o adapter comprime o prompt e retenta com sessão limpa

### Requirement: Callbacks opcionais
O adapter SHALL suportar todos os callbacks opcionais da interface: `set_progress_callback`, `set_start_agent_callback`, `set_get_agents_callback`, `set_get_demand_state_callback`, `set_read_journal_callback`, `set_send_image_callback`, `set_learn_lesson_callback`, `set_get_pipeline_state_callback`, `set_advance_step_callback`, `set_skip_step_callback`, `set_rerun_step_callback`.

#### Scenario: Callback de progresso
- **WHEN** o agente Agno chama a tool `report_progress`
- **THEN** o `_progress_callback` é invocado com o nome do agente e a mensagem

### Requirement: Construção de prompt
O adapter SHALL montar o prompt completo incluindo: contexto do workspace, system instructions (AGENTS.md), contexto adicional e prompt do usuário — na mesma ordem e formato do `ClaudeAgentSDKAdapter._build_prompt()`.

#### Scenario: Prompt com contexto completo
- **WHEN** `run()` recebe context com workspace_context, system_instructions e campos extras
- **THEN** o prompt é montado com seções "Contexto do Projeto", instruções do sistema, "Contexto" e o prompt original
