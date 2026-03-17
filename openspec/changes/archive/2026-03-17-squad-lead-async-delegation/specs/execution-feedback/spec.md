## MODIFIED Requirements

### Requirement: Feedback durante execucao de agentes background
O engine SHALL enviar feedback ao usuario durante execucao de agentes em background, combinando report_progress dos agentes com notificacoes automaticas de estado.

#### Scenario: Agente background reporta progresso
- **WHEN** um agente em background chama report_progress("Gerando proposal.md")
- **THEN** o engine MUST enviar a mensagem ao Telegram imediatamente com label do agente

#### Scenario: Feedback generico como fallback
- **WHEN** um agente em background nao chama report_progress por mais de 30 segundos
- **THEN** o engine MUST enviar feedback generico com tempo decorrido

#### Scenario: Notificacao de conclusao
- **WHEN** um agente background conclui
- **THEN** o engine MUST enviar notificacao ao usuario informando conclusao e resultado resumido
