## MODIFIED Requirements

### Requirement: Arquivo centralizado platform.yaml
O sistema SHALL usar `platform.yaml` como arquivo único de configuração para: `ai_provider` (provider de IA), `messaging_provider` (provider de mensageria), parâmetros globais e configurações por persona.

#### Scenario: Carregamento de configuração
- **WHEN** a plataforma inicia
- **THEN** platform.yaml é carregado e validado antes de qualquer componente ser instanciado

#### Scenario: Configuração inválida rejeitada
- **WHEN** platform.yaml contém um `ai_provider` não registrado
- **THEN** o sistema emite erro claro e recusa iniciar

#### Scenario: Validação de token Copilot
- **WHEN** `ai_provider` é `copilot` e `GITHUB_TOKEN` não está definido
- **THEN** a validação retorna `GITHUB_TOKEN` na lista de tokens ausentes (warning, não bloqueante — pode usar CLI login)
