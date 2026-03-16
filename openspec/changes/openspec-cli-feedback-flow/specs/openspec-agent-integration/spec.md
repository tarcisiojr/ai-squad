## ADDED Requirements

### Requirement: PO usa openspec CLI para gerar artefatos
O PO Agent SHALL usar o CLI openspec para criar changes e gerar artefatos no formato padrao.

#### Scenario: PO cria change
- **WHEN** o PO inicia especificacao de uma demanda
- **THEN** MUST executar `openspec new change "<slug-da-demanda>"` no workspace

#### Scenario: PO gera proposal seguindo instrucoes
- **WHEN** o PO precisa criar proposal.md
- **THEN** MUST executar `openspec instructions proposal --change "<nome>"` para obter o template e instrucoes, e gerar o arquivo seguindo o formato

#### Scenario: PO gera specs seguindo instrucoes
- **WHEN** o proposal esta completo
- **THEN** MUST executar `openspec instructions specs --change "<nome>"` e gerar os arquivos de specs

#### Scenario: PO gera design seguindo instrucoes
- **WHEN** as specs estao completas
- **THEN** MUST executar `openspec instructions design --change "<nome>"` e gerar o design.md

#### Scenario: PO gera tasks
- **WHEN** o design esta completo
- **THEN** MUST executar `openspec instructions tasks --change "<nome>"` e gerar o tasks.md

### Requirement: Squad Lead valida artefatos antes de avancar
O Squad Lead SHALL verificar que todos os artefatos SDD existem antes de passar para o Dev.

#### Scenario: Validacao via openspec status
- **WHEN** o PO finaliza a especificacao
- **THEN** o Squad Lead MUST executar `openspec status --change "<nome>"` e verificar que todos os artefatos estao completos

#### Scenario: Artefatos incompletos
- **WHEN** openspec status mostra artefatos incompletos
- **THEN** o Squad Lead MUST instruir o PO a completar os artefatos faltantes

### Requirement: Dev implementa a partir do tasks.md
O Dev Agent SHALL ler o tasks.md gerado pelo PO e implementar task por task.

#### Scenario: Dev le tasks
- **WHEN** o Dev inicia implementacao
- **THEN** MUST ler o tasks.md da change e implementar cada task marcando como concluida

#### Scenario: Dev marca progresso
- **WHEN** o Dev completa uma task
- **THEN** MUST alterar `- [ ]` para `- [x]` no tasks.md
