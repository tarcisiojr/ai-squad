## MODIFIED Requirements

### Requirement: Seleção de provider de IA
O sistema DEVE apresentar opções de provider de IA com default para Anthropic, incluindo Copilot.

#### Scenario: Seleção com default
- **WHEN** o wizard apresenta a escolha de provider
- **THEN** as opções são: Anthropic (default), Agno, Copilot, OpenAI

#### Scenario: Usuário aceita default
- **WHEN** o usuário pressiona Enter sem escolher
- **THEN** o sistema usa Anthropic como provider

### Requirement: Coleta de token via prompt seguro
O sistema DEVE solicitar o token do provider escolhido sem exibir o valor digitado (hide_input), exceto para Copilot onde o token é opcional.

#### Scenario: Token informado (providers com token obrigatório)
- **WHEN** o wizard solicita o token para anthropic, openai ou agno
- **THEN** o input é mascarado e o token é obrigatório

#### Scenario: Token vazio rejeitado (providers com token obrigatório)
- **WHEN** o usuário envia token vazio para anthropic, openai ou agno
- **THEN** o sistema exibe erro e solicita novamente

#### Scenario: Copilot sem token (auth via CLI)
- **WHEN** o provider é Copilot
- **THEN** o wizard pula a etapa de token OU aceita GITHUB_TOKEN opcional, informando que auth via `copilot auth login` é o método principal

#### Scenario: Copilot com GITHUB_TOKEN opcional
- **WHEN** o provider é Copilot e o usuário informa um GITHUB_TOKEN
- **THEN** o sistema aceita o token e o usa para autenticação

### Requirement: Reaproveitamento do token no .env
O sistema DEVE usar o mesmo token coletado no wizard para gerar E para preencher o `.env` do time criado.

#### Scenario: Token salvo no .env
- **WHEN** a geração é concluída com sucesso
- **THEN** o `.env` contém o token real (não placeholder) na variável correspondente ao provider (CLAUDE_CODE_OAUTH_TOKEN, GOOGLE_API_KEY, ou OPENAI_API_KEY)

#### Scenario: Credenciais do canal no .env
- **WHEN** o canal é Telegram e o usuário informou bot token e chat id
- **THEN** o `.env` contém TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID com os valores reais

#### Scenario: Copilot sem token no .env
- **WHEN** o provider é Copilot e nenhum GITHUB_TOKEN foi informado
- **THEN** o `.env` NÃO contém placeholder de token AI (apenas credenciais do canal)
