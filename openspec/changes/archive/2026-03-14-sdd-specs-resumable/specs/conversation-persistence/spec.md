## ADDED Requirements

### Requirement: Salvamento de histórico de conversa
O engine SHALL salvar cada mensagem da conversa agente ↔ usuário em arquivo persistente.

#### Scenario: Mensagem do agente salva
- **WHEN** o agente responde ao usuário
- **THEN** o sistema MUST salvar a mensagem em `state/<demand-id>/conversation.json` com role "agent", conteúdo, timestamp e nome do agente

#### Scenario: Resposta do usuário salva
- **WHEN** o usuário responde ao agente
- **THEN** o sistema MUST salvar a mensagem em `state/<demand-id>/conversation.json` com role "user", conteúdo e timestamp

#### Scenario: Escrita atômica
- **WHEN** o histórico é salvo
- **THEN** MUST usar escrita atômica (temp + rename) para evitar corrupção

### Requirement: Carregamento de histórico para retomada
O engine SHALL carregar o histórico de conversa existente ao retomar uma demanda.

#### Scenario: Retomada com histórico
- **WHEN** uma demanda é retomada após restart
- **THEN** o sistema MUST carregar `state/<demand-id>/conversation.json` e incluir as mensagens anteriores no prompt do agente

#### Scenario: Histórico inexistente
- **WHEN** não existe conversation.json para a demanda
- **THEN** MUST iniciar conversa do zero

### Requirement: Limite de histórico no contexto
O sistema SHALL limitar o número de mensagens enviadas no prompt para evitar estouro de contexto.

#### Scenario: Histórico longo
- **WHEN** a conversa excede 20 mensagens
- **THEN** MUST enviar apenas as últimas 20 mensagens no prompt, com resumo das anteriores
