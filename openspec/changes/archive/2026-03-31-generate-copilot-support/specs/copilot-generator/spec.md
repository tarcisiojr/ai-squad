## ADDED Requirements

### Requirement: CopilotGenerator implementa GeneratorProvider
O sistema DEVE implementar `CopilotGenerator` em `src/cli/generators/copilot.py` herdando de `GeneratorProvider`, usando o Copilot SDK (`copilot-sdk`) para gerar presets.

#### Scenario: Geração via Copilot com auth CLI
- **WHEN** o usuário escolhe provider Copilot e já fez `copilot auth login`
- **THEN** o sistema instancia `CopilotClient`, envia o prompt e retorna a resposta da IA

#### Scenario: Geração via Copilot com GITHUB_TOKEN
- **WHEN** a variável `GITHUB_TOKEN` está definida no ambiente
- **THEN** o sistema usa o token para autenticar com o Copilot SDK

#### Scenario: SDK não instalado
- **WHEN** o SDK copilot-sdk não está instalado
- **THEN** o sistema exibe mensagem clara: "Instale com: pip install -e '.[copilot]'"

#### Scenario: Auth não configurada
- **WHEN** nem `GITHUB_TOKEN` está definido nem `copilot auth login` foi executado
- **THEN** o sistema exibe mensagem orientando: "Execute 'copilot auth login' ou defina GITHUB_TOKEN"
