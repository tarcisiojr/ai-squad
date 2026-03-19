## ADDED Requirements

### Requirement: Interface base GeneratorProvider
O sistema DEVE definir uma ABC `GeneratorProvider` com método `generate(prompt: str) → str` que retorna a resposta da IA.

#### Scenario: Interface com contrato definido
- **WHEN** um novo provider de geração é implementado
- **THEN** ele herda de `GeneratorProvider` e implementa o método `generate`

### Requirement: Provider Anthropic
O sistema DEVE implementar `AnthropicGenerator` que usa o SDK `anthropic` com modelo `claude-haiku-4-5-20251001` por default.

#### Scenario: Geração via Anthropic
- **WHEN** o usuário escolhe provider Anthropic e informa o token
- **THEN** o sistema faz chamada via `anthropic.Anthropic(api_key=token).messages.create()` com modelo haiku

#### Scenario: SDK não instalado
- **WHEN** o SDK anthropic não está instalado
- **THEN** o sistema exibe mensagem clara: "Instale o SDK: pip install anthropic"

### Requirement: Provider OpenAI
O sistema DEVE implementar `OpenAIGenerator` que usa o SDK `openai` com modelo `gpt-4o-mini` por default.

#### Scenario: Geração via OpenAI
- **WHEN** o usuário escolhe provider OpenAI e informa o token
- **THEN** o sistema faz chamada via SDK openai com modelo gpt-4o-mini

#### Scenario: SDK não instalado
- **WHEN** o SDK openai não está instalado
- **THEN** o sistema exibe mensagem clara: "Instale o SDK: pip install openai"

### Requirement: Provider Agno
O sistema DEVE implementar `AgnoGenerator` que usa o SDK `agno` com modelo default do provider.

#### Scenario: Geração via Agno
- **WHEN** o usuário escolhe provider Agno e informa o token
- **THEN** o sistema faz chamada via SDK agno

#### Scenario: SDK não instalado
- **WHEN** o SDK agno não está instalado
- **THEN** o sistema exibe mensagem clara: "Instale o SDK: pip install agno"

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
