## ADDED Requirements

### Requirement: Comando generate no CLI
O sistema DEVE expor o comando `ai-squad generate` via Click que inicia um wizard interativo no terminal.

#### Scenario: Execução do wizard completo
- **WHEN** o usuário executa `ai-squad generate`
- **THEN** o sistema coleta sequencialmente: descrição do time, provider de IA, token, canal de comunicação, credenciais do canal, opção de knowledge base e nome do time

#### Scenario: Comando acessível via CLI
- **WHEN** o usuário executa `ai-squad --help`
- **THEN** o comando `generate` aparece na lista de comandos disponíveis

### Requirement: Coleta de descrição do time
O sistema DEVE solicitar uma descrição em texto livre do time desejado como primeira pergunta do wizard.

#### Scenario: Descrição informada
- **WHEN** o wizard solicita a descrição
- **THEN** o usuário pode digitar texto livre descrevendo o time (ex: "Time de suporte técnico que faz triagem e resolve problemas")

#### Scenario: Descrição vazia
- **WHEN** o usuário envia descrição vazia
- **THEN** o sistema exibe erro e solicita novamente

### Requirement: Seleção de provider de IA
O sistema DEVE apresentar opções de provider de IA com default para Anthropic.

#### Scenario: Seleção com default
- **WHEN** o wizard apresenta a escolha de provider
- **THEN** as opções são: Anthropic (default), Agno, OpenAI

#### Scenario: Usuário aceita default
- **WHEN** o usuário pressiona Enter sem escolher
- **THEN** o sistema usa Anthropic como provider

### Requirement: Coleta de token via prompt seguro
O sistema DEVE solicitar o token do provider escolhido sem exibir o valor digitado (hide_input).

#### Scenario: Token informado
- **WHEN** o wizard solicita o token
- **THEN** o input é mascarado (não ecoa no terminal)

#### Scenario: Token vazio
- **WHEN** o usuário envia token vazio
- **THEN** o sistema exibe erro e solicita novamente

### Requirement: Seleção de canal de comunicação
O sistema DEVE apresentar opções de canal com default para Telegram.

#### Scenario: Opções de canal
- **WHEN** o wizard apresenta a escolha de canal
- **THEN** as opções são: Telegram (default), Google Chat, CLI

### Requirement: Coleta condicional de credenciais do canal
O sistema DEVE solicitar credenciais específicas conforme o canal escolhido.

#### Scenario: Canal Telegram selecionado
- **WHEN** o usuário escolhe Telegram
- **THEN** o sistema solicita TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID

#### Scenario: Canal CLI selecionado
- **WHEN** o usuário escolhe CLI
- **THEN** o sistema NÃO solicita credenciais adicionais do canal

### Requirement: Opção de knowledge base
O sistema DEVE perguntar se o usuário deseja habilitar knowledge base, com default para não.

#### Scenario: Knowledge base desabilitado (default)
- **WHEN** o usuário pressiona Enter na pergunta de knowledge base
- **THEN** knowledge base NÃO é habilitado no config.yaml

#### Scenario: Knowledge base habilitado
- **WHEN** o usuário responde sim
- **THEN** config.yaml inclui `knowledge.enabled: true` e o diretório `knowledge/` é criado

### Requirement: Coleta do nome do time
O sistema DEVE solicitar o nome do time como última pergunta antes da geração.

#### Scenario: Nome válido
- **WHEN** o usuário informa um nome
- **THEN** o sistema usa esse nome para criar o diretório `.ai-squad/`

#### Scenario: Time já existe
- **WHEN** o nome informado já existe como `.ai-squad/` no diretório corrente
- **THEN** o sistema exibe erro informando que já existe

### Requirement: Reaproveitamento do token no .env
O sistema DEVE usar o mesmo token coletado no wizard para gerar E para preencher o `.env` do time criado.

#### Scenario: Token salvo no .env
- **WHEN** a geração é concluída com sucesso
- **THEN** o `.env` contém o token real (não placeholder) na variável correspondente ao provider (CLAUDE_CODE_OAUTH_TOKEN, GOOGLE_API_KEY, ou OPENAI_API_KEY)

#### Scenario: Credenciais do canal no .env
- **WHEN** o canal é Telegram e o usuário informou bot token e chat id
- **THEN** o `.env` contém TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID com os valores reais
