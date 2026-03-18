## MODIFIED Requirements

### Requirement: Interface ABC do barramento
O sistema SHALL definir uma classe abstrata `MessageBus` com os métodos: `send_message(user_id: str, text: str, *, thread_id: int | None = None)`, `send_approval_request(user_id: str, question: str, options: list[str], *, thread_id: int | None = None) -> str`, `ask_user(user_id: str, question: str, *, thread_id: int | None = None) -> str`, `receive_message(callback: Callable)`, `receive_voice(callback: Callable)`, `notify(user_id: str, text: str, *, thread_id: int | None = None)`, `send_photo(user_id: str, photo_path: str, caption: str, *, thread_id: int | None = None)`, `send_typing(user_id: str, *, thread_id: int | None = None)`. O barramento SHALL incluir o método `create_thread(chat_id: str, title: str) -> int | None` para criação de tópicos. Implementações sem suporte a threads SHALL retornar None em `create_thread` e ignorar `thread_id`.

#### Scenario: Envio de mensagem de texto em tópico
- **WHEN** o orquestrador chama `send_message(chat_id, texto, thread_id=123)` via interface
- **THEN** a mensagem é entregue no tópico 123 do chat

#### Scenario: Envio de mensagem sem thread_id
- **WHEN** o orquestrador chama `send_message(chat_id, texto)` sem thread_id
- **THEN** a mensagem é entregue no chat principal (comportamento atual preservado)

#### Scenario: Criação de tópico no Telegram
- **WHEN** o sistema chama `create_thread(chat_id, "Login OAuth")`
- **THEN** o Telegram cria um Forum Topic e retorna o thread_id (int)

#### Scenario: Criação de tópico em provider sem suporte
- **WHEN** o sistema chama `create_thread` no CLIMessageBus
- **THEN** o método retorna None e nenhuma ação é tomada

#### Scenario: Solicitação de aprovação em tópico
- **WHEN** o orquestrador chama `send_approval_request(chat_id, pergunta, opções, thread_id=123)`
- **THEN** os botões inline são enviados no tópico 123 e a resposta é capturada

#### Scenario: Recebimento de mensagem de texto
- **WHEN** o usuário envia uma mensagem de texto no canal
- **THEN** o callback registrado via `receive_message` é invocado com user_id e texto

#### Scenario: Recebimento de mensagem de voz
- **WHEN** o usuário envia uma mensagem de voz no canal
- **THEN** o áudio é transcrito e o callback registrado via `receive_voice` é invocado com user_id e texto transcrito

### Requirement: Implementação Telegram
O sistema SHALL fornecer `TelegramMessageBus` como implementação concreta de `MessageBus`. Cada persona SHALL ter sua própria instância com token, nome e avatar. A transcrição de voz SHALL usar Whisper/OpenAI. O handler de mensagens SHALL extrair `message_thread_id` e `from_user.id` de cada update e propagar via callback. O método `_send` SHALL aceitar e propagar `message_thread_id` para a API do Telegram. O método `create_thread` SHALL chamar `bot.create_forum_topic(chat_id, name)` e retornar o `message_thread_id` resultante.

#### Scenario: Persona PO envia mensagem em tópico
- **WHEN** a persona PO envia uma mensagem com thread_id=123
- **THEN** a mensagem é enviada usando o token do bot PO no tópico 123

#### Scenario: Transcrição de áudio via Whisper
- **WHEN** o usuário envia áudio ao bot Telegram
- **THEN** o áudio é baixado, enviado ao Whisper API e o texto transcrito é retornado ao callback

#### Scenario: Handler extrai thread_id e user_id
- **WHEN** uma mensagem chega no handler _handle_text
- **THEN** o callback recebe o texto, o user_id (from_user.id) e o thread_id (message_thread_id)

### Requirement: Implementação CLI para testes locais
O sistema SHALL fornecer `CLIMessageBus` como implementação para desenvolvimento e testes locais, sem dependência de serviço externo. `create_thread` SHALL retornar None. O parâmetro `thread_id` SHALL ser ignorado em todos os métodos.

#### Scenario: Teste local sem Telegram
- **WHEN** o desenvolvedor configura `messaging_provider: cli`
- **THEN** mensagens são exibidas no terminal, thread_id é ignorado, create_thread retorna None
