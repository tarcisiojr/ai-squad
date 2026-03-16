## MODIFIED Requirements

### Requirement: Ciclo de demanda com checkpoints
O OrchestrationEngine SHALL salvar checkpoint ao concluir cada fase do ciclo, permitindo retomada parcial.

#### Scenario: Checkpoint após PO concluir
- **WHEN** o PO finaliza especificação e usuário aprova
- **THEN** o engine MUST salvar o plano aprovado no checkpoint antes de iniciar fase Dev

#### Scenario: Retomada após crash na fase Dev
- **WHEN** o daemon reinicia e a demanda estava em "dev_working"
- **THEN** o engine MUST carregar o plano do checkpoint e continuar a fase Dev sem re-executar o PO

#### Scenario: Conversa iterativa com histórico persistido
- **WHEN** o agente e o usuário trocam mensagens durante _agent_conversation
- **THEN** cada mensagem MUST ser salva no conversation.json da demanda

## ADDED Requirements

### Requirement: Injeção de contexto do produto no despacho de agentes
O engine SHALL coletar e injetar contexto do projeto no prompt antes de despachar qualquer agente.

#### Scenario: Contexto injetado no prompt do PO
- **WHEN** o engine despacha o PO para especificação
- **THEN** o prompt MUST incluir contexto do produto (README, estrutura, specs anteriores)

#### Scenario: Contexto injetado no prompt do Dev
- **WHEN** o engine despacha o Dev para implementação
- **THEN** o prompt MUST incluir contexto do produto
