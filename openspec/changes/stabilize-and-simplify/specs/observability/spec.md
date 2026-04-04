## ADDED Requirements

### Requirement: Progress streaming ao usuário
O sistema SHALL enviar as últimas 3 mensagens de progresso ao usuário a cada 15 segundos, com prefixo do nome do agente. Mensagens duplicadas SHALL ser filtradas.

#### Scenario: Progresso periódico enviado
- **WHEN** um agente reporta 5 mensagens de progresso em 15 segundos
- **THEN** as últimas 3 mensagens são enviadas ao usuário com formato "[Agente] mensagem"

#### Scenario: Sem progresso não gera mensagem
- **WHEN** nenhum agente reporta progresso em um ciclo de 15 segundos
- **THEN** nenhuma mensagem de progresso é enviada ao usuário

### Requirement: Logging estruturado em arquivo
O sistema SHALL configurar um logger com handler de arquivo rotativo (`logs/agent.log`, 5MB, 3 backups). SDK stderr SHALL ser redirecionado para `logger.debug` com prefixo `[sdk]`.

#### Scenario: Log rotativo criado
- **WHEN** o daemon inicia
- **THEN** o diretório `logs/` é criado e `agent.log` recebe output do SDK

#### Scenario: Rotação por tamanho
- **WHEN** `agent.log` atinge 5MB
- **THEN** o arquivo é rotacionado para `agent.log.1` e um novo `agent.log` é criado

### Requirement: Token tracking por chamada
O sistema SHALL logar `input_tokens`, `output_tokens`, `model` e `duration_ms` para cada chamada ao adapter. Os totais acumulados SHALL ser expostos via comando `/status`.

#### Scenario: Tokens logados após chamada
- **WHEN** o adapter completa uma chamada ao SDK
- **THEN** o log contém uma linha com input_tokens, output_tokens, model e duration_ms

#### Scenario: Status mostra totais de tokens
- **WHEN** o usuário executa `/status`
- **THEN** a resposta inclui total de tokens usados na sessão atual (input + output)
