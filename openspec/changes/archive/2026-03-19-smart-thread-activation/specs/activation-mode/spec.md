## ADDED Requirements

### Requirement: Configuração de activation_mode
O sistema DEVE suportar campo `activation_mode` no config.yaml com valores `mention`, `all` ou `command`, com default `mention`.

#### Scenario: Default é mention
- **WHEN** o config.yaml não define `activation_mode`
- **THEN** o sistema usa `mention` como default

#### Scenario: Valor inválido
- **WHEN** o config.yaml define `activation_mode: invalido`
- **THEN** o sistema exibe erro na inicialização informando os valores válidos

### Requirement: Filtro de menção em grupo/espaço
O sistema DEVE filtrar mensagens em grupos/espaços conforme o `activation_mode` configurado, ignorando mensagens que não ativam o bot.

#### Scenario: Modo mention — mensagem sem menção em grupo
- **WHEN** `activation_mode: mention` e uma mensagem sem @bot chega no grupo
- **THEN** o bot ignora a mensagem e NÃO invoca o callback do daemon

#### Scenario: Modo mention — mensagem com menção em grupo
- **WHEN** `activation_mode: mention` e uma mensagem com @bot chega no grupo
- **THEN** o bot processa a mensagem normalmente via callback

#### Scenario: Modo all — qualquer mensagem em grupo
- **WHEN** `activation_mode: all` e qualquer mensagem chega no grupo
- **THEN** o bot processa todas as mensagens (comportamento atual)

#### Scenario: Modo command — mensagem com comando
- **WHEN** `activation_mode: command` e uma mensagem com prefixo `/` chega
- **THEN** o bot processa a mensagem

#### Scenario: Modo command — mensagem sem comando
- **WHEN** `activation_mode: command` e uma mensagem sem prefixo `/` chega no grupo
- **THEN** o bot ignora a mensagem

### Requirement: DM sempre responde
O sistema DEVE processar todas as mensagens em chats 1:1 (DM), independente do `activation_mode` configurado.

#### Scenario: DM com activation_mode mention
- **WHEN** `activation_mode: mention` e uma mensagem chega em DM (sem menção)
- **THEN** o bot processa a mensagem normalmente

### Requirement: Pending reply ignora activation mode
O sistema DEVE capturar a próxima mensagem quando há um pending reply (approval/ask_user), independente de menção ou comando.

#### Scenario: Aprovação sem menção
- **WHEN** o bot enviou pedido de aprovação e o usuário responde "Aprovado" sem @bot
- **THEN** o bot captura a resposta e resolve o pending reply

### Requirement: Detecção de menção por provider
Cada provider de mensageria DEVE implementar detecção de menção usando os mecanismos nativos da plataforma.

#### Scenario: Telegram detecta menção via entities
- **WHEN** uma mensagem chega no Telegram com entity type `mention` contendo `@bot_username`
- **THEN** a mensagem é identificada como menção ao bot

#### Scenario: GChat detecta menção via annotations
- **WHEN** uma mensagem chega no GChat com annotation de userMention tipo BOT
- **THEN** a mensagem é identificada como menção ao bot

#### Scenario: CLI sempre ativa
- **WHEN** o provider é CLI
- **THEN** todas as mensagens são tratadas como ativação (CLI é 1:1)
