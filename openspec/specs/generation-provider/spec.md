## ADDED Requirements

### Requirement: Provider Copilot no registro
O sistema DEVE registrar o provider "copilot" em `PROVIDER_CONFIGS` com `ai_provider="copilot"`, `env_var=""` e `default_model=""`.

#### Scenario: Copilot selecionado
- **WHEN** o provider é Copilot
- **THEN** config.yaml usa `ai_provider: copilot` e .env NÃO contém placeholder de token AI

#### Scenario: get_provider retorna CopilotGenerator
- **WHEN** `get_provider("copilot", token)` é chamado
- **THEN** o sistema retorna instância de `CopilotGenerator`

## MODIFIED Requirements

### Requirement: Mapeamento provider → configuração do time
O sistema DEVE mapear o provider de geração para a configuração do time (ai_provider e env var correspondente).

#### Scenario: Anthropic selecionado
- **WHEN** o provider é Anthropic
- **THEN** config.yaml usa `ai_provider: claude-agent-sdk` e .env usa `CLAUDE_CODE_OAUTH_TOKEN`

#### Scenario: Agno selecionado
- **WHEN** o provider é Agno
- **THEN** config.yaml usa `ai_provider: agno` e .env usa `GOOGLE_API_KEY`

#### Scenario: OpenAI selecionado
- **WHEN** o provider é OpenAI
- **THEN** config.yaml usa `ai_provider: openai` e .env usa `OPENAI_API_KEY`

#### Scenario: Copilot selecionado
- **WHEN** o provider é Copilot
- **THEN** config.yaml usa `ai_provider: copilot` e .env NÃO contém variável de token AI
