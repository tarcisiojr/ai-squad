## ADDED Requirements

### Requirement: PathResolver resolve caminhos por modo
O sistema SHALL ter uma classe PathResolver que resolve workspace, agents_dir, state_dir, config_path, pipeline_dir, env_path e global_skills_dir baseado no modo de execução (local ou docker).

#### Scenario: Modo local resolve caminhos relativos ao projeto
- **WHEN** PathResolver é criado com mode="local" e base_dir="/home/user/projeto"
- **THEN** workspace SHALL ser "/home/user/projeto"
- **THEN** agents_dir SHALL ser "/home/user/projeto/.ai-squad/agents"
- **THEN** state_dir SHALL ser "/home/user/projeto/.ai-squad/state"
- **THEN** config_path SHALL ser "/home/user/projeto/.ai-squad/config.yaml"
- **THEN** pipeline_dir SHALL ser "/home/user/projeto/.ai-squad/pipeline"
- **THEN** env_path SHALL ser "/home/user/projeto/.ai-squad/.env"

#### Scenario: Modo docker resolve caminhos absolutos do container
- **WHEN** PathResolver é criado com mode="docker"
- **THEN** workspace SHALL ser "/workspace"
- **THEN** agents_dir SHALL ser "/app/agents"
- **THEN** state_dir SHALL ser "/app/state"
- **THEN** config_path SHALL ser "/app/config.yaml"
- **THEN** pipeline_dir SHALL ser "/app/pipeline"

#### Scenario: Skills globais resolvem para home do usuario no modo local
- **WHEN** PathResolver é criado com mode="local"
- **THEN** global_skills_dir SHALL ser "~/.ai-squad/skills"
