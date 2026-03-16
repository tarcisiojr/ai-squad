## MODIFIED Requirements

### Requirement: Conversa com agente em dois modos
O OrchestrationEngine SHALL suportar modo CHAT (texto livre) e modo APPROVAL (com botões), alternando com base em marcadores no texto do agente.

#### Scenario: Modo CHAT padrão
- **WHEN** o agente responde sem marcador de conclusão
- **THEN** o engine MUST enviar resposta como texto e aguardar resposta livre do usuário

#### Scenario: Transição para modo APPROVAL
- **WHEN** o agente inclui marcador de conclusão na resposta
- **THEN** o engine MUST mostrar botões [Aprovar] [Rejeitar] junto com a resposta (sem marcador)

### Requirement: Labels de agentes da configuração
O engine SHALL ler nomes e avatares dos agentes da configuração, não de constantes hardcoded.

#### Scenario: Nome e avatar da config
- **WHEN** o engine exibe mensagem de um agente
- **THEN** MUST usar `name` e `avatar` da persona correspondente no config.yaml

## ADDED Requirements

### Requirement: Fluxo OpenSpec no ciclo de demanda
O engine SHALL seguir o framework OpenSpec no ciclo de demanda, salvando artefatos no workspace.

#### Scenario: Ciclo completo
- **WHEN** uma demanda é processada
- **THEN** o engine MUST seguir: PO (conversa → proposal.md) → Dev (implementa → design.md) → QA (valida contra specs)
