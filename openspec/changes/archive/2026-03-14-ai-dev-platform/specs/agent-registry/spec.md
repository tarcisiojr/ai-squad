## ADDED Requirements

### Requirement: Catálogo YAML de agentes
O sistema SHALL manter um `registry.yaml` que cataloga cada agente com: nome, domínio, protocolo, ferramentas disponíveis, versão e adapter preferido. O registry SHALL ser a fonte única de verdade sobre agentes disponíveis.

#### Scenario: Listagem de agentes disponíveis
- **WHEN** o orquestrador consulta o registry para uma feature do domínio "web"
- **THEN** o registry retorna os agentes cujo domínio inclui "web", ordenados por prioridade

### Requirement: Estrutura de agente
Cada agente SHALL ter um diretório com: `AGENTS.md` (fonte única de contexto), `skills/` (diretório de skills), `tools.yaml` (ferramentas declaradas). `CLAUDE.md`, `GEMINI.md`, `COPILOT.md` SHALL ser symlinks para `AGENTS.md` commitados no git.

#### Scenario: Agente PO com symlinks
- **WHEN** o agente PO é carregado
- **THEN** CLAUDE.md, GEMINI.md e COPILOT.md apontam para AGENTS.md via symlink e o conteúdo é idêntico

### Requirement: Matching de agente por domínio
O orquestrador SHALL selecionar agentes pelo match entre o contrato da feature (domínio declarado) e o domínio registrado no `registry.yaml`. Se múltiplos agentes correspondem, SHALL usar o de maior prioridade.

#### Scenario: Feature web matched com dev-web
- **WHEN** uma feature com domínio "web" precisa ser desenvolvida
- **THEN** o registry retorna o subagente `dev-web` como responsável

### Requirement: Personas base e subagentes
O registry SHALL incluir personas base: `po`, `dev-orchestrator`, `qa`. Subagentes dev especializados SHALL estar disponíveis por domínio: web, mobile, desktop, embedded, firmware.

#### Scenario: Personas base sempre presentes
- **WHEN** o registry é carregado
- **THEN** as personas po, dev-orchestrator e qa estão registradas e funcionais

### Requirement: Extensibilidade de agentes
Adicionar novo agente SHALL exigir apenas: criar diretório do agente + adicionar entrada no `registry.yaml`. Nenhuma outra modificação de código SHALL ser necessária.

#### Scenario: Adição de agente dev-data
- **WHEN** um novo diretório `agents/dev-data/` é criado com AGENTS.md e uma entrada adicionada ao registry.yaml
- **THEN** o agente dev-data está disponível para matching sem alteração em nenhum código existente
