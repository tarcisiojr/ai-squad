## ADDED Requirements

### Requirement: Geração de pipeline.yaml via IA
O sistema DEVE gerar um pipeline.yaml válido a partir da descrição do time, seguindo o schema do projeto (steps com id, name, agent/agents, type, execution, model_tier, file).

#### Scenario: Pipeline gerado com steps válidos
- **WHEN** a IA recebe a descrição "Time de suporte técnico com triagem e resolução"
- **THEN** o pipeline.yaml gerado contém steps com campos obrigatórios (id, name, agent, type, execution, model_tier, file) e referências corretas aos step files

#### Scenario: Checkpoints em pontos críticos
- **WHEN** o pipeline é gerado
- **THEN** pelo menos um step tem `type: checkpoint` para aprovação humana

### Requirement: Geração de AGENTS.md por agente
O sistema DEVE gerar um AGENTS.md para cada agente definido no pipeline, seguindo a estrutura padrão (Dominio, Quando Envolver, Responsabilidades, Criterios de Aceite, Restricoes, Instrucoes, Comunicacao).

#### Scenario: AGENTS.md com seções obrigatórias
- **WHEN** o pipeline define um agente "triager"
- **THEN** o arquivo `agents/triager/AGENTS.md` é gerado com todas as seções padrão preenchidas com conteúdo relevante ao domínio

#### Scenario: Squad Lead sempre incluído
- **WHEN** qualquer time é gerado
- **THEN** o diretório `agents/squad-lead/AGENTS.md` é criado com persona de coordenador

### Requirement: Geração de step files com quality gates
O sistema DEVE gerar step files (.md) para cada step do pipeline, contendo: Inputs, Expected Outputs, Quality Gate e Veto Conditions.

#### Scenario: Step file com quality gate
- **WHEN** um step "triagem" é definido no pipeline
- **THEN** o arquivo `pipeline/steps/step-01-triagem.md` contém seções de Quality Gate com checklist verificável e Veto Conditions

### Requirement: Geração de config.yaml completo
O sistema DEVE gerar config.yaml com todos os campos necessários, incluindo ai_provider, messaging_provider, ai_model, agent_timeout, squad_lead e agents.

#### Scenario: Config com agents auto-populados
- **WHEN** a IA gera 3 agentes (triager, resolver, escalation)
- **THEN** config.yaml contém os 3 agentes com name, avatar e command

#### Scenario: Config com knowledge habilitado
- **WHEN** o usuário habilitou knowledge base no wizard
- **THEN** config.yaml contém `knowledge: {enabled: true, use_qmd: false, knowledge_dir: "knowledge/"}`

### Requirement: Prompt de geração com exemplos
O sistema DEVE enviar à IA um prompt contendo: a descrição do usuário, a estrutura esperada de output (JSON), e exemplo de um preset real como referência.

#### Scenario: Prompt inclui exemplo de preset
- **WHEN** a chamada de geração é feita
- **THEN** o prompt inclui a estrutura de um preset existente como exemplo do formato esperado

### Requirement: Criação da estrutura de diretórios
O sistema DEVE criar a estrutura completa `.ai-squad/` com todos os arquivos gerados, pronta para `ai-squad start`.

#### Scenario: Estrutura completa criada
- **WHEN** a geração é concluída com sucesso
- **THEN** o diretório `.ai-squad/` contém: config.yaml, .env, pipeline/pipeline.yaml, pipeline/steps/*.md, agents/*/AGENTS.md e state/

#### Scenario: Mensagem de sucesso com próximo passo
- **WHEN** o time é criado com sucesso
- **THEN** o sistema exibe resumo (agentes, steps, checkpoints) e o comando `ai-squad start <nome>`
