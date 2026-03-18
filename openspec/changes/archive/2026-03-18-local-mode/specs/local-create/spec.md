## ADDED Requirements

### Requirement: Create sem --repo cria estrutura local
O sistema SHALL criar estrutura .ai-squad/ no diretório corrente quando "ai-squad create" é executado sem a flag --repo.

#### Scenario: Criação local gera estrutura correta
- **WHEN** usuário executa "ai-squad create MeuTime" sem --repo
- **THEN** sistema SHALL criar ./.ai-squad/ no diretório corrente
- **THEN** SHALL conter config.yaml, .env, agents/, pipeline/, state/
- **THEN** SHALL NOT conter docker-compose.yml nem whisper/

#### Scenario: Config local não tem repo_path
- **WHEN** time é criado em modo local
- **THEN** config.yaml SHALL NOT conter campo repo_path
- **THEN** workspace SHALL ser o diretório pai do .ai-squad/

#### Scenario: Erro se .ai-squad já existe
- **WHEN** usuário executa "ai-squad create MeuTime" sem --repo
- **WHEN** ./.ai-squad/ já existe
- **THEN** sistema SHALL exibir erro "Já existe uma squad neste diretório"

### Requirement: Create com --repo mantém comportamento Docker
O sistema SHALL manter o comportamento atual quando "ai-squad create" é executado com --repo, criando em ~/.ai-squad/teams/.

#### Scenario: Criação Docker gera estrutura completa
- **WHEN** usuário executa "ai-squad create MeuTime --repo ~/app"
- **THEN** sistema SHALL criar ~/.ai-squad/teams/MeuTime/
- **THEN** SHALL conter config.yaml, .env, agents/, pipeline/, state/, docker-compose.yml, whisper/
- **THEN** config.yaml SHALL conter repo_path apontando para ~/app
