## ADDED Requirements

### Requirement: Estrutura de contratos por repo
O sistema SHALL manter um diretório `specs/` como guarda-chuva com submodulos git dos repositórios do projeto. Cada submodulo SHALL conter contratos firmados antes do desenvolvimento: OpenAPI, AsyncAPI e schemas de eventos.

#### Scenario: PO commita contrato antes do desenvolvimento
- **WHEN** o PO finaliza a especificação de uma feature
- **THEN** os contratos (OpenAPI/AsyncAPI/schemas) são commitados no submodulo correspondente em specs/ antes de qualquer dev iniciar

### Requirement: Validação de contratos no CI
O CI do specs SHALL validar que nenhum PR de submodulo quebra os contratos registrados. PRs que introduzem breaking changes nos contratos SHALL ser rejeitados automaticamente.

#### Scenario: PR quebra contrato OpenAPI
- **WHEN** um PR modifica um endpoint removendo um campo obrigatório do contrato OpenAPI
- **THEN** o CI falha e o PR é bloqueado com mensagem indicando a quebra de contrato

#### Scenario: PR compatível com contratos
- **WHEN** um PR adiciona funcionalidade respeitando o contrato existente
- **THEN** o CI passa e o PR pode ser mergeado

### Requirement: Desenvolvimento paralelo via contratos
Os contratos firmados SHALL eliminar dependências de runtime entre submodulos, permitindo desenvolvimento em paralelo. Cada submodulo SHALL ter seu próprio AGENTS.md, skills/ e symlinks.

#### Scenario: Dois submodulos desenvolvidos em paralelo
- **WHEN** dois subagentes dev trabalham em submodulos diferentes que compartilham um contrato AsyncAPI
- **THEN** ambos desenvolvem em paralelo sem conflito, pois o contrato garante compatibilidade

### Requirement: Estrutura de submodulo
Cada submodulo SHALL conter: `AGENTS.md` (contexto do agente para aquele repo), `skills/` (skills específicas), symlinks `CLAUDE.md`/`GEMINI.md`/`COPILOT.md` → `AGENTS.md`.

#### Scenario: Submodulo com estrutura completa
- **WHEN** um novo submodulo é adicionado ao specs/
- **THEN** ele contém AGENTS.md, skills/, e os symlinks commitados no git
