## MODIFIED Requirements

### Requirement: Mensagem padrao para Squad Lead
O daemon SHALL direcionar mensagens sem comando para o Squad Lead.

#### Scenario: Mensagem sem comando
- **WHEN** o usuario envia mensagem sem prefixo de comando
- **THEN** a mensagem MUST ser enviada ao Squad Lead (nao mais como demanda generica)

#### Scenario: Comando de agente especifico
- **WHEN** o usuario envia mensagem com /<comando>
- **THEN** MUST direcionar para o agente correspondente ao comando
