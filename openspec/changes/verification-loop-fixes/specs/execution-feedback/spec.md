## MODIFIED Requirements

### Requirement: Feedback durante execucao de agentes background
O engine SHALL enviar mensagens de conclusao com conteudo suficiente para o usuario entender o resultado, sem truncar prematuramente.

#### Scenario: Mensagem de conclusao com conteudo completo
- **WHEN** um agente conclui e o engine envia notificacao
- **THEN** a mensagem MUST conter ate 2000 caracteres do resultado (nao 200)

#### Scenario: Mensagem de verificacao falhou
- **WHEN** a verificacao de um agente falha
- **THEN** o engine MUST enviar mensagem informando o que faltou (ex: "3 tasks pendentes no tasks.md")
