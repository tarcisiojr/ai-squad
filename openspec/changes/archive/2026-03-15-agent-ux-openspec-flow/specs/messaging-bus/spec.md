## MODIFIED Requirements

### Requirement: Envio de texto plano
O TelegramMessageBus SHALL enviar todas as mensagens como texto plano, sem parse_mode Markdown.

#### Scenario: Mensagem sem formatação
- **WHEN** o bus envia mensagem ao Telegram
- **THEN** MUST enviar sem parse_mode (texto plano)

#### Scenario: Caracteres especiais preservados
- **WHEN** a mensagem contém caracteres como `_`, `*`, `[`, `]`
- **THEN** MUST exibi-los literalmente, sem tentar interpretar como formatação
