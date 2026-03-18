## ADDED Requirements

### Requirement: Start detecta modo automaticamente
O sistema SHALL detectar automaticamente o modo de execução (local ou docker) baseado na presença de .ai-squad/ no diretório corrente.

#### Scenario: Detecta modo local quando .ai-squad existe no cwd
- **WHEN** usuário executa "ai-squad start MeuTime"
- **WHEN** ./.ai-squad/ existe no diretório corrente
- **THEN** sistema SHALL iniciar em modo local (foreground)

#### Scenario: Detecta modo Docker quando .ai-squad não existe
- **WHEN** usuário executa "ai-squad start MeuTime"
- **WHEN** ./.ai-squad/ não existe no diretório corrente
- **WHEN** ~/.ai-squad/teams/MeuTime/ existe
- **THEN** sistema SHALL iniciar em modo Docker (background, container)

#### Scenario: Erro quando nenhum modo encontrado
- **WHEN** usuário executa "ai-squad start MeuTime"
- **WHEN** ./.ai-squad/ não existe
- **WHEN** ~/.ai-squad/teams/MeuTime/ não existe
- **THEN** sistema SHALL exibir erro com orientação para criar o time

### Requirement: Flags --local e --docker forçam modo
O sistema SHALL aceitar flags --local e --docker no comando start para forçar o modo de execução.

#### Scenario: Flag --local força modo local
- **WHEN** usuário executa "ai-squad start MeuTime --local"
- **THEN** sistema SHALL iniciar em modo local independente da detecção automática

#### Scenario: Flag --docker força modo Docker
- **WHEN** usuário executa "ai-squad start MeuTime --docker"
- **THEN** sistema SHALL iniciar em modo Docker independente da detecção automática

#### Scenario: Flags são mutuamente exclusivas
- **WHEN** usuário executa "ai-squad start MeuTime --local --docker"
- **THEN** sistema SHALL exibir erro "Flags --local e --docker são mutuamente exclusivas"
