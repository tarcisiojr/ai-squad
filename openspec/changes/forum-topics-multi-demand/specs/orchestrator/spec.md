## MODIFIED Requirements

### Requirement: Máquina de estados do ciclo de vida
O orquestrador SHALL gerenciar o ciclo de vida de cada demanda através dos estados definidos no pipeline. Cada demanda SHALL ter seu próprio demand_id gerado no momento da criação (não mais um ID fixo compartilhado). O daemon SHALL gerar demand_id real via `_generate_demand_id` para toda nova demanda, inclusive as originadas pelo Squad Lead. O ID fixo "squad-lead-session" SHALL ser usado exclusivamente para conversa livre no Tópico Geral (sem pipeline associado).

#### Scenario: Ciclo completo com tópico isolado
- **WHEN** uma nova demanda é recebida em grupo-fórum e todos os passos são aprovados
- **THEN** a demanda transiciona pelos estados em seu próprio demand_id com tópico associado

#### Scenario: Conversa livre sem demanda
- **WHEN** o usuário envia mensagem no Tópico Geral sem iniciar demanda
- **THEN** o Squad Lead responde usando sessão geral sem criar demand_id nem tópico

#### Scenario: Transição inválida rejeitada
- **WHEN** uma tentativa de transição inválida é feita
- **THEN** o sistema rejeita a transição e mantém o estado atual

### Requirement: Roteamento de decisões humanas
O orquestrador SHALL interceptar chamadas `ask()` dos agentes e rotear para o barramento via `MessageBus`, propagando o `thread_id` da demanda. Perguntas de aprovação em checkpoints SHALL ser enviadas ao tópico correto da demanda.

#### Scenario: Agente solicita aprovação em tópico
- **WHEN** o agente PO emite pedido de aprovação para demanda com thread_id=123
- **THEN** o orquestrador envia a pergunta via `send_approval_request(chat_id, pergunta, opções, thread_id=123)`

#### Scenario: Agente solicita aprovação sem tópico (fallback)
- **WHEN** o agente emite pedido de aprovação para demanda sem thread_id
- **THEN** o orquestrador envia a pergunta no chat principal (comportamento atual)

### Requirement: Persistência de estado
O orquestrador SHALL persistir o estado de cada demanda em arquivo JSON. O estado SHALL sobreviver a reinicializações do sistema. O state SHALL incluir o campo `created_by` com o user_id do criador.

#### Scenario: Recuperação após reinício
- **WHEN** o sistema reinicia com demandas ativas em tópicos
- **THEN** o orquestrador carrega estados do JSON, o daemon carrega mapeamento thread↔demand, e respostas de agentes continuam indo para os tópicos corretos

### Requirement: Despacho de agentes via adapter
O orquestrador SHALL disparar agentes exclusivamente via `AIAgentAdapter` interface. Ao despachar, o engine SHALL associar o `thread_id` ao `RunningAgent` para que callbacks de resultado sejam roteados corretamente.

#### Scenario: Despacho de agente com thread_id
- **WHEN** uma demanda com thread_id=123 dispara um agente
- **THEN** o RunningAgent é criado com thread_id=123 e mensagens de progresso/resultado vão para esse tópico
