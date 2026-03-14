## ADDED Requirements

### Requirement: Interface ABC do barramento
O sistema SHALL definir uma classe abstrata `MessageBus` com os métodos: `send_message(user_id: str, text: str)`, `send_approval_request(user_id: str, question: str, options: list[str]) -> str`, `receive_message(callback: Callable)`, `receive_voice(callback: Callable)`, `notify(user_id: str, text: str)`. Nenhum componente externo ao barramento SHALL importar implementações concretas.

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

### Requirement: Implementação Telegram
O sistema SHALL fornecer `TelegramMessageBus` como implementação concreta de `MessageBus`. Cada persona (PO, Dev, QA) SHALL ter sua própria instância com token, nome e avatar separados. A transcrição de voz SHALL usar Whisper/OpenAI.

#### Scenario: Persona PO envia mensagem
- **WHEN** a persona PO envia uma mensagem via barramento Telegram
- **THEN** a mensagem é enviada usando o token e identidade do bot PO

#### Scenario: Transcrição de áudio via Whisper
- **WHEN** o usuário envia áudio ao bot Telegram
- **THEN** o áudio é baixado, enviado ao Whisper API e o texto transcrito é retornado ao callback

### Requirement: Seleção de implementação via configuração
O sistema SHALL selecionar a implementação do barramento baseado no campo `messaging_provider` do `platform.yaml`. Adicionar novo provider SHALL exigir apenas: novo arquivo de implementação + entrada no platform.yaml.

#### Scenario: Troca de provider Telegram para CLI
- **WHEN** `platform.yaml` tem `messaging_provider: cli`
- **THEN** o sistema instancia `CLIMessageBus` sem alteração em nenhum outro componente

### Requirement: Implementação CLI para testes locais
O sistema SHALL fornecer `CLIMessageBus` como implementação para desenvolvimento e testes locais, sem dependência de serviço externo de mensageria.

#### Scenario: Teste local sem Telegram
- **WHEN** o desenvolvedor configura `messaging_provider: cli`
- **THEN** mensagens são exibidas no terminal e entrada é lida do stdin
