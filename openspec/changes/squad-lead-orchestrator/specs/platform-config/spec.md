## MODIFIED Requirements

### Requirement: Config com squad_lead e agents
O config.yaml SHALL separar squad_lead (obrigatorio) de agents (configuraveis).

#### Scenario: Config com squad_lead
- **WHEN** o config.yaml e carregado
- **THEN** MUST ter secao squad_lead com name e avatar

#### Scenario: Config com agents
- **WHEN** o config.yaml lista agents
- **THEN** cada agent MUST ter name, avatar, e command

#### Scenario: Agente sem command explicito
- **WHEN** um agent nao define command no config
- **THEN** MUST gerar automaticamente como /<nome-do-agente>
