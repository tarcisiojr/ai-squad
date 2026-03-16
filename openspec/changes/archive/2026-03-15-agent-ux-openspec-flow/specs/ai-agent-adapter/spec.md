## MODIFIED Requirements

### Requirement: Suporte a tools no adapter SDK
O ClaudeAgentSDKAdapter SHALL suportar configuração de tools permitidas por agente.

#### Scenario: PO com web search
- **WHEN** o adapter é configurado com `allowed_tools=["web_search"]`
- **THEN** o SDK MUST habilitar busca web durante a execução do agente

#### Scenario: Timeout configurável por chamada
- **WHEN** o adapter recebe `timeout` maior que o padrão
- **THEN** MUST usar o timeout fornecido em vez do padrão da config
