## ADDED Requirements

### Requirement: CLI principal ai-dev-team
O sistema SHALL fornecer um CLI chamado `ai-dev-team` instalável via `pip install` com entry point registrado no pyproject.toml.

#### Scenario: CLI disponível após instalação
- **WHEN** o usuário executa `pip install -e .` ou `pip install ai-dev-team`
- **THEN** o comando `ai-dev-team` MUST estar disponível no PATH

#### Scenario: Ajuda exibida sem argumentos
- **WHEN** o usuário executa `ai-dev-team` sem argumentos ou com `--help`
- **THEN** o sistema MUST exibir lista de comandos disponíveis com descrições

### Requirement: Comando create
O sistema SHALL fornecer o comando `ai-dev-team create <nome> --repo <caminho>` que cria a estrutura completa de um novo time.

#### Scenario: Criação de time com sucesso
- **WHEN** o usuário executa `ai-dev-team create backend-api --repo ~/projetos/minha-api`
- **THEN** o sistema MUST criar `~/.ai-dev-team/teams/backend-api/` com config.yaml, .env template, docker-compose.yml e diretório state/

#### Scenario: Time já existe
- **WHEN** o usuário tenta criar um time com nome que já existe
- **THEN** o sistema MUST exibir erro informando que o time já existe e sugerir usar outro nome

#### Scenario: Repo não existe
- **WHEN** o caminho do repo fornecido não existe
- **THEN** o sistema MUST exibir erro informando que o diretório não foi encontrado

### Requirement: Comando start
O sistema SHALL fornecer o comando `ai-dev-team start <nome>` que sobe o container Docker do time.

#### Scenario: Start de time específico
- **WHEN** o usuário executa `ai-dev-team start backend-api`
- **THEN** o sistema MUST executar `docker-compose up -d` no diretório do time

#### Scenario: Start de todos os times
- **WHEN** o usuário executa `ai-dev-team start --all`
- **THEN** o sistema MUST executar start para cada time existente

#### Scenario: Start sem .env preenchido
- **WHEN** o usuário tenta start mas o .env contém valores placeholder
- **THEN** o sistema MUST exibir erro listando as variáveis que precisam ser preenchidas

### Requirement: Comando stop
O sistema SHALL fornecer o comando `ai-dev-team stop <nome>` que para o container Docker do time.

#### Scenario: Stop de time específico
- **WHEN** o usuário executa `ai-dev-team stop backend-api`
- **THEN** o sistema MUST executar `docker-compose down` no diretório do time

#### Scenario: Stop de todos os times
- **WHEN** o usuário executa `ai-dev-team stop --all`
- **THEN** o sistema MUST executar stop para cada time em execução

### Requirement: Comando list
O sistema SHALL fornecer o comando `ai-dev-team list` que exibe todos os times e seus status.

#### Scenario: Listar times
- **WHEN** o usuário executa `ai-dev-team list`
- **THEN** o sistema MUST exibir tabela com nome, repo, e status (running/stopped) de cada time

#### Scenario: Nenhum time criado
- **WHEN** não existem times criados
- **THEN** o sistema MUST exibir mensagem informando e sugerindo o comando create

### Requirement: Comando logs
O sistema SHALL fornecer o comando `ai-dev-team logs <nome>` para ver logs do container.

#### Scenario: Ver logs
- **WHEN** o usuário executa `ai-dev-team logs backend-api`
- **THEN** o sistema MUST exibir logs do container com `docker-compose logs -f`

#### Scenario: Logs com limite
- **WHEN** o usuário executa `ai-dev-team logs backend-api --tail 100`
- **THEN** o sistema MUST exibir apenas as últimas 100 linhas de log

### Requirement: Comando status
O sistema SHALL fornecer o comando `ai-dev-team status <nome>` para ver demandas ativas do time.

#### Scenario: Ver status de demandas
- **WHEN** o usuário executa `ai-dev-team status backend-api`
- **THEN** o sistema MUST exibir lista de demandas ativas com ID, descrição e estado atual
