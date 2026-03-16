## MODIFIED Requirements

### Requirement: Carregamento de configuração
O PlatformConfig SHALL carregar configuração tanto de arquivo YAML quanto de variáveis de ambiente, com variáveis de ambiente tendo precedência.

#### Scenario: Config via YAML
- **WHEN** o sistema inicia com config.yaml presente
- **THEN** MUST carregar todas as configurações do arquivo

#### Scenario: Config via variáveis de ambiente
- **WHEN** variáveis de ambiente como CLAUDE_CODE_OAUTH_TOKEN e GITHUB_TOKEN estão definidas
- **THEN** MUST usar os valores das variáveis de ambiente, sobrescrevendo valores do YAML

#### Scenario: Config com .env file
- **WHEN** um arquivo .env existe no diretório de trabalho
- **THEN** MUST carregar variáveis do .env antes de processar o config.yaml

### Requirement: Repo path na configuração
O config.yaml SHALL incluir campo `repo_path` indicando o repositório alvo.

#### Scenario: Repo path resolvido
- **WHEN** o config.yaml contém `repo_path: ~/projetos/app`
- **THEN** MUST resolver para caminho absoluto e validar que o diretório existe

## ADDED Requirements

### Requirement: Validação de configuração obrigatória
O sistema SHALL validar que todas as configurações obrigatórias estão preenchidas antes de iniciar.

#### Scenario: Token não preenchido
- **WHEN** CLAUDE_CODE_OAUTH_TOKEN contém valor placeholder ou está vazio
- **THEN** MUST falhar com erro claro listando os tokens que precisam ser preenchidos

#### Scenario: Todas as configs válidas
- **WHEN** todos os tokens obrigatórios estão preenchidos e repo_path existe
- **THEN** MUST iniciar normalmente
