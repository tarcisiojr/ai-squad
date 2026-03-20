## ADDED Requirements

### Requirement: Implementação CopilotAdapter
O sistema SHALL fornecer `CopilotAdapter` em `src/adapters/copilot_adapter.py` que implementa `AIAgentAdapter` usando o GitHub Copilot SDK (`github-copilot-sdk`). O adapter SHALL usar a subscription Copilot da organização para autenticação.

#### Scenario: Execução de agente via Copilot SDK
- **WHEN** `CopilotAdapter.run(prompt, context)` é chamado
- **THEN** o adapter cria ou retoma uma session no Copilot SDK, envia o prompt via `send_and_wait` e retorna `response.data.content`

#### Scenario: Instanciação sem API key externa
- **WHEN** o adapter Copilot é instanciado
- **THEN** ele usa `GITHUB_TOKEN` do ambiente ou credenciais do `copilot auth login`, sem exigir API keys de providers de IA

### Requirement: Tools de orquestração via MCP stdio
O adapter SHALL expor as 11 tools de orquestração do AI Squad reutilizando `SquadMCPToolsServer` como MCP server stdio na configuração `mcp_servers` da session do Copilot SDK.

#### Scenario: Tools disponíveis na session
- **WHEN** uma session é criada no CopilotAdapter
- **THEN** as 11 tools (report_progress, start_agent, get_running_agents, get_demand_state, get_pipeline_state, advance_step, skip_step, rerun_step, read_journal, send_image, learn_lesson) estão disponíveis via MCP

#### Scenario: Agente chama tool de orquestração
- **WHEN** o modelo invoca `start_agent("po", "Especificar demanda")` via MCP
- **THEN** o `SquadMCPToolsServer` delega para o callback registrado pelo engine e retorna o resultado

### Requirement: Sessions persistentes via session_id
O adapter SHALL usar `demand_id` do contexto como `session_id` do Copilot SDK para manter sessions persistentes. O adapter SHALL retomar sessions existentes via `resume_session`.

#### Scenario: Continuidade de conversa
- **WHEN** `run()` é chamado com um `demand_id` que já possui session ativa
- **THEN** o adapter retoma a session existente preservando histórico de conversa

#### Scenario: Nova demanda cria nova session
- **WHEN** `run()` é chamado com um `demand_id` sem session prévia
- **THEN** o adapter cria nova session com `session_id` igual ao `demand_id`

### Requirement: Autenticação via subscription da org
O adapter SHALL suportar dois modos de autenticação: (1) `GITHUB_TOKEN` como variável de ambiente, (2) credenciais do CLI via `use_logged_in_user=True`. O adapter SHALL NOT suportar BYOK (Bring Your Own Key).

#### Scenario: Auth via GITHUB_TOKEN
- **WHEN** `GITHUB_TOKEN` está definido no ambiente
- **THEN** o adapter usa esse token como `github_token` no `CopilotClient`

#### Scenario: Auth via CLI login
- **WHEN** `GITHUB_TOKEN` não está definido mas o usuário fez `copilot auth login`
- **THEN** o adapter usa `use_logged_in_user=True` e funciona com as credenciais do CLI

### Requirement: Model routing por session
O adapter SHALL suportar `model_override` no contexto para trocar o modelo por execução, permitindo model routing (fast/powerful) sem recriar o client.

#### Scenario: Override de modelo para step rápido
- **WHEN** `context` contém `model_override: "gpt-4.1-mini"`
- **THEN** a session é criada com o modelo override em vez do modelo padrão

### Requirement: Retry com backoff exponencial
O adapter SHALL implementar retry com backoff exponencial (2/4/8s) para erros transientes, mesmo padrão dos adapters existentes. Timeout SHALL NOT fazer retry.

#### Scenario: Erro transiente com retry
- **WHEN** a execução falha com erro transiente (não timeout)
- **THEN** o adapter retenta até 3 vezes com backoff 2s, 4s, 8s

#### Scenario: Timeout sem retry
- **WHEN** a execução excede o timeout configurado
- **THEN** o adapter lança `TimeoutError` sem retentar

### Requirement: Client lifecycle gerenciado
O adapter SHALL inicializar o `CopilotClient` de forma lazy (no primeiro `run()`) e SHALL fornecer método `shutdown()` para cleanup do client.

#### Scenario: Lazy init do client
- **WHEN** `run()` é chamado pela primeira vez
- **THEN** o adapter chama `client.start()` antes da execução

#### Scenario: Shutdown limpo
- **WHEN** `shutdown()` é chamado
- **THEN** o adapter chama `client.stop()` e libera recursos
