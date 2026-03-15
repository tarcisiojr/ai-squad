"""Templates de configuração para novos times."""

CONFIG_YAML_TEMPLATE = """\
# Configuração do time ai-dev-team
ai_provider: claude-code
messaging_provider: telegram

# Timeout para execução de agentes (segundos)
agent_timeout: 300

# Diretório de persistência de estado
state_dir: state/

# Caminho do repositório alvo
repo_path: "{repo_path}"

# Configurações por persona
personas:
  po:
    name: "PO Agent"
    avatar: "📋"
  dev-orchestrator:
    name: "Dev Orchestrator"
    avatar: "🔧"
  qa:
    name: "QA Agent"
    avatar: "🧪"
"""

ENV_TEMPLATE = """\
# === Tokens obrigatórios ===

# Auth Claude Code CLI (OAuth token)
CLAUDE_CODE_OAUTH_TOKEN=PREENCHA_AQUI_token_oauth_claude

# GitHub (para criar PRs e push)
GITHUB_TOKEN=PREENCHA_AQUI_token_github

# Telegram Bot (criado via @BotFather)
TELEGRAM_TOKEN=PREENCHA_AQUI_token_bot_telegram

# Chat ID do Telegram (grupo ou chat privado)
TELEGRAM_CHAT_ID=PREENCHA_AQUI_chat_id_telegram

# === Opcional ===

# OpenAI API key (para transcrição de voz via Whisper)
# OPENAI_API_KEY=PREENCHA_AQUI_api_key_openai
"""

DOCKER_COMPOSE_TEMPLATE = """\
services:
  ai-dev-team-{team_name}:
    image: ai-dev-team:latest
    container_name: adt-{team_name}
    restart: unless-stopped

    volumes:
      # Repositório alvo
      - {repo_path}:/workspace

      # Docker socket do host (para agentes subirem infra)
      - /var/run/docker.sock:/var/run/docker.sock

      # Persistência de estado
      - ./state:/app/state

      # Configurações git do host (agent = uid 1000)
      - ~/.ssh:/home/agent/.ssh:ro
      - ~/.gitconfig:/home/agent/.gitconfig:ro

    env_file:
      - .env

    environment:
      - TEAM_NAME={team_name}

    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "2.0"
"""

# Valor placeholder para detectar .env não preenchido
PLACEHOLDER_PREFIX = "PREENCHA_AQUI_"

# Variáveis obrigatórias que devem ser preenchidas
REQUIRED_ENV_VARS = [
    "CLAUDE_CODE_OAUTH_TOKEN",
    "GITHUB_TOKEN",
    "TELEGRAM_TOKEN",
    "TELEGRAM_CHAT_ID",
]
