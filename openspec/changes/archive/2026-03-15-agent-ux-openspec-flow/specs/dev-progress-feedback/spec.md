## ADDED Requirements

### Requirement: Feedback periódico durante execução longa
O engine SHALL enviar notificações de progresso quando um agente demora mais que 30 segundos.

#### Scenario: Dev trabalhando por mais de 30s
- **WHEN** o agente Dev está executando há mais de 30 segundos sem responder
- **THEN** o engine MUST enviar "Dev trabalhando..." no Telegram a cada 30 segundos

#### Scenario: Timeout estendido para Dev
- **WHEN** o agente Dev está executando
- **THEN** o timeout MUST ser de pelo menos 600 segundos (10 minutos)

### Requirement: Verificação de resultado do Dev
O engine SHALL verificar se o Dev produziu mudanças reais no workspace.

#### Scenario: Dev sem mudanças
- **WHEN** o Dev marca ---DONE--- mas não há mudanças no workspace (git status limpo)
- **THEN** o engine MUST notificar o usuário que nenhuma alteração foi detectada e pedir para o Dev tentar novamente
