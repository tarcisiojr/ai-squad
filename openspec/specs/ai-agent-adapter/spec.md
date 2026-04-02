## MODIFIED Requirements

### Requirement: Seleção de adapter via configuração
O sistema SHALL selecionar o adapter de IA baseado no campo `ai_provider` do `platform.yaml`. Adicionar novo provider SHALL exigir apenas: novo arquivo de implementação + entrada no platform.yaml. Valores suportados: `claude-agent-sdk`, `agno`, `copilot`.

#### Scenario: Troca de Claude Code para Gemini
- **WHEN** `platform.yaml` tem `ai_provider: gemini`
- **THEN** o sistema instancia `GeminiAdapter` sem alteração em nenhum outro componente

#### Scenario: Seleção do adapter Copilot
- **WHEN** `platform.yaml` tem `ai_provider: copilot`
- **THEN** o sistema instancia `CopilotAdapter` sem alteração em nenhum outro componente

#### Scenario: Dependência Copilot não instalada
- **WHEN** `ai_provider: copilot` mas `github-copilot-sdk` não está instalado
- **THEN** o sistema emite erro claro com instrução de instalação e recusa iniciar
