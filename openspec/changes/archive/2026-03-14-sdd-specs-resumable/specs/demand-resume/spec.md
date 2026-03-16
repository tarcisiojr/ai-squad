## ADDED Requirements

### Requirement: Detecção de demandas pendentes no startup
O daemon SHALL verificar demandas com estado não-terminal ao iniciar.

#### Scenario: Demanda pendente detectada
- **WHEN** o daemon inicia e existe `state/<demand-id>.json` com estado diferente de "done" ou "idle"
- **THEN** MUST re-enfileirar a demanda para processamento

#### Scenario: Notificação de retomada
- **WHEN** o daemon retoma uma demanda pendente
- **THEN** MUST notificar o usuário via Telegram: "Retomando demanda <id> da fase <estado>"

#### Scenario: Nenhuma demanda pendente
- **WHEN** não existem demandas com estado não-terminal
- **THEN** MUST iniciar normalmente sem re-enfileirar

### Requirement: Checkpoint de progresso por fase
O engine SHALL salvar checkpoint ao entrar em cada fase do ciclo.

#### Scenario: Checkpoint salvo na transição
- **WHEN** o engine transiciona para um novo estado
- **THEN** MUST salvar em `state/<demand-id>.json` o estado atual, fase, e resultados parciais das fases concluídas

#### Scenario: Retomada do checkpoint
- **WHEN** uma demanda é retomada com estado "dev_working"
- **THEN** MUST pular a fase do PO (já concluída) e continuar do dev, usando o plano salvo no checkpoint

### Requirement: Graceful handling de estado corrompido
O daemon SHALL tratar estados corrompidos sem travar.

#### Scenario: JSON corrompido
- **WHEN** um arquivo de estado não pode ser parseado
- **THEN** MUST logar erro, notificar via Telegram, e ignorar a demanda corrompida
