## ADDED Requirements

### Requirement: Coleta de contexto do produto
O engine SHALL coletar contexto do repositório alvo antes de enviar prompts aos agentes.

#### Scenario: Leitura de README
- **WHEN** o engine prepara contexto para um agente
- **THEN** MUST incluir o conteúdo de `/workspace/README.md` se existir

#### Scenario: Estrutura de diretórios
- **WHEN** o engine prepara contexto para um agente
- **THEN** MUST incluir a árvore de diretórios do workspace até 2 níveis de profundidade

#### Scenario: Specs existentes
- **WHEN** existem artefatos em `/workspace/specs/`
- **THEN** MUST incluir lista de demandas anteriores e seus títulos (lidos do proposal.md de cada uma)

### Requirement: Limite de contexto
O contexto do produto SHALL respeitar um limite de tokens para não sobrecarregar o prompt.

#### Scenario: Truncamento de README grande
- **WHEN** o README.md excede 4000 caracteres
- **THEN** MUST truncar e adicionar indicador "[truncado]"

#### Scenario: Projeto sem README
- **WHEN** o README.md não existe
- **THEN** MUST usar apenas estrutura de diretórios como contexto

### Requirement: Injeção de contexto no prompt
O contexto coletado SHALL ser injetado na seção "Contexto do Projeto" do prompt enviado ao agente.

#### Scenario: Prompt com contexto
- **WHEN** o engine envia prompt ao adapter
- **THEN** o prompt MUST conter seção "## Contexto do Projeto" antes da seção "## Tarefa"
