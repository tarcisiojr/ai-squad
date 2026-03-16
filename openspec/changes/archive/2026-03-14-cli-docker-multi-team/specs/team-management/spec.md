## ADDED Requirements

### Requirement: Estrutura de diretórios por time
O sistema SHALL criar e gerenciar a estrutura `~/.ai-dev-team/teams/<nome>/` para cada time.

#### Scenario: Estrutura criada no create
- **WHEN** um novo time é criado
- **THEN** o sistema MUST criar a seguinte estrutura:
  ```
  ~/.ai-dev-team/teams/<nome>/
  ├── config.yaml
  ├── .env
  ├── docker-compose.yml
  └── state/
  ```

### Requirement: Config.yaml por time
O sistema SHALL gerar um `config.yaml` com configurações padrão sensatas para cada time.

#### Scenario: Config gerado com defaults
- **WHEN** o time é criado com `--repo ~/projetos/app`
- **THEN** o config.yaml MUST conter: ai_provider (claude-code), messaging_provider (telegram), agent_timeout (300), state_dir (state/), repo_path (caminho absoluto do repo), e seção personas com PO, Dev e QA

### Requirement: Template .env
O sistema SHALL gerar um `.env` com placeholders claros para cada token obrigatório.

#### Scenario: .env gerado com placeholders
- **WHEN** o time é criado
- **THEN** o .env MUST conter placeholders para CLAUDE_CODE_OAUTH_TOKEN, GITHUB_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, e OPENAI_API_KEY (marcado como opcional)

#### Scenario: Placeholders identificáveis
- **WHEN** o .env é gerado
- **THEN** cada valor placeholder MUST seguir o padrão `PREENCHA_AQUI_<descrição>` para ser detectável pelo comando start

### Requirement: Isolamento entre times
Cada time SHALL operar de forma completamente independente dos demais.

#### Scenario: Times não compartilham estado
- **WHEN** dois times estão rodando simultaneamente
- **THEN** o estado (demandas, worktrees) de um MUST NOT afetar o outro

#### Scenario: Start/stop independente
- **WHEN** o usuário para um time
- **THEN** os demais times MUST continuar rodando normalmente
