## ADDED Requirements

### Requirement: Geração de artefatos SDD no repositório
O engine SHALL criar artefatos SDD dentro do repositório alvo em `specs/<demand-id>/` durante o ciclo de demanda.

#### Scenario: PO gera proposal no workspace
- **WHEN** o PO finaliza a especificação de uma demanda
- **THEN** o sistema MUST salvar o resultado em `/workspace/specs/<demand-id>/proposal.md`

#### Scenario: Dev gera design no workspace
- **WHEN** o Dev elabora o design técnico
- **THEN** o sistema MUST salvar em `/workspace/specs/<demand-id>/design.md`

### Requirement: Estrutura de diretório por demanda
Cada demanda SHALL ter seu próprio subdiretório em `specs/` para evitar conflitos.

#### Scenario: Criação de diretório da demanda
- **WHEN** uma nova demanda inicia o ciclo
- **THEN** o sistema MUST criar `/workspace/specs/<demand-id>/` antes de iniciar o PO

#### Scenario: Demandas paralelas não conflitam
- **WHEN** duas demandas estão em andamento simultaneamente
- **THEN** cada uma MUST ter seu subdiretório separado em `specs/`

### Requirement: Artefatos versionáveis via git
Os artefatos gerados SHALL ser commitáveis no repositório do projeto.

#### Scenario: Artefatos em formato markdown
- **WHEN** o agente gera um artefato
- **THEN** o artefato MUST ser um arquivo markdown válido legível por humanos
