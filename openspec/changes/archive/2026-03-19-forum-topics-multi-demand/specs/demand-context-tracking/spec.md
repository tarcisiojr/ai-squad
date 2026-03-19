## ADDED Requirements

### Requirement: MessageContext como unidade de contexto
O sistema SHALL usar um dataclass `MessageContext` para encapsular `chat_id`, `user_id`, `thread_id` e `demand_id` em todas as interações entre daemon, engine e callbacks. Nenhum componente SHALL passar `chat_id` como string solta quando `thread_id` for relevante.

#### Scenario: Mensagem recebida em grupo-fórum
- **WHEN** o daemon recebe uma mensagem com chat_id, from_user.id e message_thread_id
- **THEN** um MessageContext é criado com os três valores e o demand_id resolvido via mapeamento

#### Scenario: Mensagem recebida em DM
- **WHEN** o daemon recebe uma mensagem em DM (sem thread_id)
- **THEN** um MessageContext é criado com thread_id=None e demand_id do modo flat

### Requirement: Separação de chat_id e user_id
O sistema SHALL distinguir `chat_id` (identificador do chat/grupo) de `user_id` (identificador de quem enviou a mensagem). Em grupos, esses valores são diferentes. O handler de mensagens SHALL extrair `from_user.id` do update do Telegram como `user_id`.

#### Scenario: Mensagem em grupo
- **WHEN** o usuário "Maria" (user_id=111) envia mensagem no grupo (chat_id=999)
- **THEN** o sistema registra user_id=111 como autora e chat_id=999 como destino de respostas

#### Scenario: Mensagem em DM
- **WHEN** o usuário envia mensagem em DM
- **THEN** chat_id e user_id são iguais (comportamento atual preservado)

### Requirement: Atribuição de demanda ao criador
O sistema SHALL registrar o `user_id` de quem criou cada demanda no state da demanda. Essa informação SHALL ser persistida junto com o demand state.

#### Scenario: Tarcísio cria demanda
- **WHEN** o usuário com user_id=111 envia "Cria login OAuth" e o Squad Lead cria a demanda
- **THEN** o state da demanda registra created_by=111

#### Scenario: Consulta de demandas por criador
- **WHEN** o Squad Lead precisa listar demandas e seus donos
- **THEN** o state de cada demanda inclui o user_id do criador
