## ADDED Requirements

### Requirement: Criação automática de tópico por demanda
O sistema SHALL criar um Forum Topic no Telegram quando uma nova demanda é iniciada pelo Squad Lead em um grupo-fórum. O título do tópico SHALL conter o avatar do agente principal e uma descrição curta da demanda (máximo 128 caracteres, limite do Telegram).

#### Scenario: Nova demanda em grupo-fórum
- **WHEN** o Squad Lead delega uma tarefa via `start_agent` em um chat com `is_forum=True`
- **THEN** o sistema cria um Forum Topic com título formatado e envia mensagem inicial no tópico

#### Scenario: Nova demanda em DM ou grupo normal
- **WHEN** o Squad Lead delega uma tarefa em um chat sem suporte a fórum
- **THEN** o sistema não cria tópico e opera no modo flat (comportamento atual)

### Requirement: Roteamento de mensagens por thread_id
O sistema SHALL rotear mensagens recebidas em um Forum Topic diretamente para o `demand_id` associado àquele tópico. Mensagens no Tópico Geral (sem `message_thread_id` ou com thread_id do General) SHALL ser tratadas como conversa livre com o Squad Lead.

#### Scenario: Mensagem em tópico de demanda
- **WHEN** o usuário envia uma mensagem em um tópico mapeado ao demand_id "login-oauth-a1b2"
- **THEN** o daemon roteia a mensagem para `run_squad_lead` com demand_id "login-oauth-a1b2"

#### Scenario: Mensagem no Tópico Geral
- **WHEN** o usuário envia uma mensagem no Tópico Geral do grupo-fórum
- **THEN** o daemon roteia a mensagem para o Squad Lead com ID de sessão geral (sem pipeline associado)

#### Scenario: Mensagem em tópico sem mapeamento
- **WHEN** o usuário envia uma mensagem em um tópico que não está mapeado a nenhuma demanda
- **THEN** o daemon trata como conversa genérica com o Squad Lead

### Requirement: Persistência do mapeamento thread_id ↔ demand_id
O sistema SHALL persistir o mapeamento bidirecional entre `thread_id` (int do Telegram) e `demand_id` (string) em arquivo JSON. O mapeamento SHALL sobreviver a reinicializações do daemon.

#### Scenario: Restart do daemon com demandas ativas
- **WHEN** o daemon reinicia e existem demandas ativas com tópicos associados
- **THEN** o mapeamento é carregado do arquivo JSON e o roteamento funciona sem perda

#### Scenario: Nova demanda adiciona mapeamento
- **WHEN** uma nova demanda é criada e um tópico é gerado
- **THEN** o mapeamento é atualizado atomicamente (fsync) com o novo par thread_id ↔ demand_id

### Requirement: Respostas de agentes no tópico correto
O sistema SHALL enviar todas as mensagens de agentes (progresso, resultado, erro, imagens) no Forum Topic associado à demanda que o agente está atendendo. O `thread_id` SHALL ser propagado desde a criação da demanda até os callbacks de envio.

#### Scenario: Agente reporta progresso
- **WHEN** um agente em background chama `report_progress` para a demanda "login-oauth-a1b2"
- **THEN** a mensagem de progresso é enviada no tópico mapeado a "login-oauth-a1b2"

#### Scenario: Agente conclui tarefa
- **WHEN** um agente finaliza e o engine dispara o callback de resultado
- **THEN** o resultado é enviado no tópico correto da demanda, não no Tópico Geral
