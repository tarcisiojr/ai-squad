## ADDED Requirements

### Requirement: Modo CHAT sem botões
O engine SHALL operar em modo CHAT por padrão, enviando respostas do agente como texto puro sem botões de ação.

#### Scenario: Agente faz pergunta
- **WHEN** o agente responde sem marcador de conclusão
- **THEN** o engine MUST enviar a resposta como mensagem de texto puro no Telegram e aguardar resposta de texto livre do usuário

#### Scenario: Conversa ida e volta
- **WHEN** o usuário responde em texto livre durante modo CHAT
- **THEN** o engine MUST reenviar a resposta ao agente com histórico da conversa

### Requirement: Modo APPROVAL com botões
O engine SHALL entrar em modo APPROVAL quando detectar marcador de conclusão no texto do agente.

#### Scenario: Marcador detectado
- **WHEN** o agente inclui `---SPEC_READY---`, `---DONE---` ou `---QA_DONE---` na resposta
- **THEN** o engine MUST remover o marcador do texto, enviar a mensagem com botões [Aprovar] [Rejeitar], e aguardar clique

#### Scenario: Aprovação aceita
- **WHEN** o usuário clica Aprovar
- **THEN** o engine MUST prosseguir para a próxima fase do ciclo

#### Scenario: Rejeição com feedback
- **WHEN** o usuário clica Rejeitar
- **THEN** o engine MUST pedir feedback em texto livre e reenviar ao agente para revisão

### Requirement: Fallback por limite de turnos
O engine SHALL perguntar ao usuário se quer finalizar após N turnos sem marcador.

#### Scenario: 10 turnos sem marcador
- **WHEN** a conversa atinge 10 turnos sem marcador de conclusão
- **THEN** o engine MUST perguntar ao usuário "Deseja finalizar esta conversa?" com botões [Finalizar] [Continuar]
