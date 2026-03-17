## ADDED Requirements

### Requirement: Formato padrao de AGENTS.md
Cada agente SHALL ser definido por um arquivo AGENTS.md com secoes padronizadas.

#### Scenario: Secoes obrigatorias
- **WHEN** um AGENTS.md e criado para um novo agente
- **THEN** MUST conter as secoes: Dominio, Quando Envolver, Responsabilidades, Criterios de Aceite, Marcador de Conclusao, Restricoes, Instrucoes

#### Scenario: Squad Lead le definicoes
- **WHEN** o engine prepara o prompt do Squad Lead
- **THEN** MUST ler todos os AGENTS.md do diretorio agents/ e injetar resumo (Dominio + Quando Envolver + Criterios de Aceite) no prompt

#### Scenario: Agente customizado pelo usuario
- **WHEN** o usuario cria um novo arquivo agents/security/AGENTS.md
- **THEN** o Squad Lead MUST reconhecer o novo agente sem nenhuma alteracao de codigo

### Requirement: AGENTS.md como instrucao do agente
O conteudo completo do AGENTS.md SHALL ser injetado no prompt do agente quando ele e invocado.

#### Scenario: Instrucoes injetadas
- **WHEN** o engine invoca um agente
- **THEN** o prompt MUST conter o conteudo completo do AGENTS.md do agente como instrucao de sistema
