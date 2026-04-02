## MODIFIED Requirements

### Requirement: Interface ABC do barramento
O sistema SHALL definir uma classe abstrata `MessageBus` com os métodos: `send_message(user_id: str, text: str)`, `send_approval_request(user_id: str, question: str, options: list[str]) -> str`, `receive_message(callback: Callable)`, `receive_voice(callback: Callable)`, `notify(user_id: str, text: str)`. Nenhum componente externo ao barramento SHALL importar implementações concretas. Implementações que controlam o terminal (ex: TUI) SHALL restaurar o estado do terminal em qualquer cenário de saída via `run_forever()`.

#### Scenario: Envio de mensagem de texto
- **WHEN** o orquestrador chama `send_message(user_id, texto)` via interface
- **THEN** a mensagem é entregue ao usuário no canal configurado

#### Scenario: Solicitação de aprovação com opções
- **WHEN** o orquestrador chama `send_approval_request(user_id, pergunta, ["Aprovar", "Rejeitar"])`
- **THEN** o barramento envia a pergunta ao usuário e retorna a opção selecionada como string

#### Scenario: Recebimento de mensagem de texto
- **WHEN** o usuário envia uma mensagem de texto no canal
- **THEN** o callback registrado via `receive_message` é invocado com user_id e texto

#### Scenario: Recebimento de mensagem de voz
- **WHEN** o usuário envia uma mensagem de voz no canal
- **THEN** o áudio é transcrito e o callback registrado via `receive_voice` é invocado com user_id e texto transcrito

#### Scenario: Provider com controle de terminal encerra com erro
- **WHEN** `run_forever()` de um provider com controle de terminal lança exceção
- **THEN** o terminal é restaurado ao estado original antes do retorno
