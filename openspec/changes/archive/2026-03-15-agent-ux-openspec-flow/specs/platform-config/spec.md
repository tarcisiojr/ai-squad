## MODIFIED Requirements

### Requirement: Personas com campo command
O config.yaml SHALL incluir campo `command` em cada persona para geração dinâmica de comandos.

#### Scenario: Config com commands
- **WHEN** o config.yaml contém `command: "/po"` na persona po
- **THEN** o daemon MUST registrar `/po` como comando válido

#### Scenario: Persona sem command
- **WHEN** uma persona não define `command`
- **THEN** o daemon MUST gerar comando automaticamente como `/<nome-da-persona>`
