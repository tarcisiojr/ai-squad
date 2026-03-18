## ADDED Requirements

### Requirement: Daemon roda como processo foreground no modo local
O sistema SHALL executar o daemon como processo Python direto no terminal do usuário quando em modo local, sem Docker.

#### Scenario: Start local roda foreground
- **WHEN** usuário executa "ai-squad start MeuTime" e .ai-squad/ existe no cwd
- **THEN** daemon SHALL iniciar no processo atual (foreground)
- **THEN** logs SHALL ser exibidos no terminal em tempo real
- **THEN** processo SHALL ficar ativo até Ctrl+C

#### Scenario: Ctrl+C faz shutdown graceful
- **WHEN** daemon está rodando em modo local
- **WHEN** usuário pressiona Ctrl+C (SIGINT)
- **THEN** daemon SHALL fazer shutdown graceful (salvar estado, fechar conexões)
- **THEN** processo SHALL encerrar com exit code 0

### Requirement: Daemon carrega .env automaticamente no modo local
O sistema SHALL carregar variáveis de ambiente do arquivo .ai-squad/.env via python-dotenv antes de iniciar no modo local.

#### Scenario: Variáveis do .env são carregadas
- **WHEN** daemon inicia em modo local
- **WHEN** .ai-squad/.env existe com TELEGRAM_TOKEN=abc123
- **THEN** os.environ["TELEGRAM_TOKEN"] SHALL ser "abc123"

#### Scenario: Erro se .env não existe
- **WHEN** daemon inicia em modo local
- **WHEN** .ai-squad/.env não existe
- **THEN** sistema SHALL exibir erro orientando criar o .env

### Requirement: Daemon valida tokens antes de iniciar
O sistema SHALL validar que todas as variáveis obrigatórias estão preenchidas antes de iniciar o daemon no modo local.

#### Scenario: Tokens não preenchidos bloqueiam start
- **WHEN** daemon tenta iniciar em modo local
- **WHEN** TELEGRAM_TOKEN contém placeholder "PREENCHA_AQUI_"
- **THEN** sistema SHALL exibir erro listando variáveis faltantes
- **THEN** daemon SHALL não iniciar
