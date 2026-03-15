## ADDED Requirements

### Requirement: Daemon em loop infinito
O container SHALL executar um processo daemon que roda continuamente escutando mensagens do Telegram.

#### Scenario: Inicialização do daemon
- **WHEN** o container inicia
- **THEN** o daemon MUST inicializar factory, registrar providers, conectar ao Telegram e entrar em loop de escuta

#### Scenario: Recebimento de demanda
- **WHEN** o usuário envia mensagem no Telegram com texto de demanda
- **THEN** o daemon MUST criar uma nova demanda e iniciar o ciclo de orquestração (PO → aprovação → Dev → PR → QA → done)

#### Scenario: Múltiplas demandas
- **WHEN** uma nova demanda chega enquanto outra está em andamento
- **THEN** o daemon MUST enfileirar a nova demanda e processá-la após a atual ser concluída

### Requirement: Graceful shutdown
O daemon SHALL encerrar de forma limpa ao receber sinal de parada.

#### Scenario: SIGTERM recebido
- **WHEN** o container recebe SIGTERM (via docker-compose down)
- **THEN** o daemon MUST salvar estado das demandas ativas, notificar via Telegram que está encerrando, e finalizar o processo sem perder dados

#### Scenario: Demanda em andamento no shutdown
- **WHEN** o daemon recebe SIGTERM com uma demanda em execução
- **THEN** o daemon MUST aguardar a conclusão da etapa atual (máximo 30s), salvar estado, e permitir retomada no próximo start

### Requirement: Health check
O daemon SHALL reportar seu estado de saúde.

#### Scenario: Container health check
- **WHEN** o docker-compose verifica saúde do container
- **THEN** o daemon MUST responder via health check endpoint ou arquivo indicando que está ativo e escutando

### Requirement: Log estruturado
O daemon SHALL emitir logs estruturados para facilitar debugging.

#### Scenario: Logs de operação
- **WHEN** o daemon processa uma demanda
- **THEN** MUST emitir logs com timestamp, nível (INFO/ERROR/DEBUG), demand_id e etapa atual

#### Scenario: Logs acessíveis via CLI
- **WHEN** o usuário executa `ai-dev-team logs <nome>`
- **THEN** os logs MUST ser legíveis e filtráveis por nível
