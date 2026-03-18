"""Templates de configuração para novos times."""

CONFIG_YAML_TEMPLATE = """\
# Configuração do time ai-squad
ai_provider: claude-agent-sdk
messaging_provider: telegram

# Modelo de IA (usado quando model_tier não é configurado)
ai_model: claude-sonnet-4-20250514

# Model routing por tier (usado pelo pipeline nos steps)
# fast → steps leves (conversação, triagem)
# powerful → steps pesados (implementação, review, QA)
# light_model: claude-haiku-4-5-20251001
# heavy_model: claude-sonnet-4-20250514

# Timeout padrão para agentes (segundos)
# Agentes individuais podem sobrescrever via campo "timeout" na seção agents
agent_timeout: 300

# Diretório de persistência de estado
state_dir: state/

# Caminho do repositório alvo
repo_path: "{repo_path}"

# Squad Lead (coordenador obrigatorio)
squad_lead:
  name: "Squad Lead"
  avatar: "👨‍💼"

# Agentes do time (devem corresponder aos agents/ e pipeline)
agents:
  po:
    name: "PO Agent"
    avatar: "📋"
    command: "/po"
  dev-backend:
    name: "Dev Backend"
    avatar: "⚙️"
    command: "/dev-back"
  dev-frontend:
    name: "Dev Frontend"
    avatar: "🎨"
    command: "/dev-front"
  code-review:
    name: "Code Review"
    avatar: "🔍"
    command: "/review"
  qa:
    name: "QA Agent"
    avatar: "🧪"
    command: "/qa"
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
  ai-squad-{team_name}:
    image: ai-squad:latest
    container_name: adt-{team_name}
    restart: unless-stopped

    volumes:
      # Repositório alvo
      - {repo_path}:/workspace

      # Docker socket do host (para agentes subirem infra)
      - /var/run/docker.sock:/var/run/docker.sock

      # Persistência de estado
      - ./state:/app/state

      # Configuração do time
      - ./config.yaml:/app/config.yaml:ro

      # Agentes customizáveis (AGENTS.md + skills/)
      - ./agents:/app/agents:ro

      # Skills globais (compartilhadas por todos os times)
      - ~/.ai-squad/skills:/app/global-skills:ro

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

  whisper:
    build:
      context: {whisper_context}
    container_name: adt-{team_name}-whisper
    restart: unless-stopped
    environment:
      - WHISPER_MODEL=medium
    volumes:
      - whisper-cache:/root/.cache
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: "4.0"

volumes:
  whisper-cache:
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
