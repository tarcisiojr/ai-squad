## ADDED Requirements

### Requirement: Comandos gerados da config
O daemon SHALL gerar comandos `/<agente>` dinamicamente a partir das personas definidas no config.yaml.

#### Scenario: Personas com campo command
- **WHEN** o config.yaml contém persona com `command: "/po"`
- **THEN** o daemon MUST registrar `/po` como comando válido que direciona mensagens para o agente "po"

#### Scenario: Help dinâmico
- **WHEN** o usuário envia `/help`
- **THEN** o daemon MUST listar todos os comandos disponíveis lidos das personas do config

#### Scenario: Labels do engine da config
- **WHEN** o engine precisa exibir nome/avatar de um agente
- **THEN** MUST usar `name` e `avatar` da persona correspondente no config.yaml, não valores hardcoded
