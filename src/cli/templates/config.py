"""Templates de configuração para novos times."""

# Tokens comuns (independem do provider de mensageria)
COMMON_ENV_TEMPLATE = """\
# === Tokens obrigatórios ===

# Auth Claude Code CLI (OAuth token)
CLAUDE_CODE_OAUTH_TOKEN=PREENCHA_AQUI_token_oauth_claude

"""

# Template opcional (GitHub, Whisper/voz)
OPTIONAL_ENV_TEMPLATE = """\
# === Opcional ===

# GitHub (para criar PRs e push — necessário se agentes fazem push)
# GITHUB_TOKEN=PREENCHA_AQUI_token_github

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

      # Pipeline
      - ./pipeline:/app/pipeline:ro

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

# Template de config.yaml com opção agno + campo tools
CONFIG_YAML_AGNO_EXAMPLE = """\
# Para usar Agno como provider de IA:
# ai_provider: agno
# ai_model: gemini-2.0-flash
#
# Toolkits extras por agente (apenas com provider agno):
# agents:
#   dev:
#     name: "Dev Backend"
#     tools:
#       - web_search        # DuckDuckGo (gratuito, sem API key)
#       - code_execution    # PythonTools (sandbox em /tmp)
#       - shell             # ShellTools (working dir)
#     # web_search_provider: tavily  # Alternativa: tavily, serpapi
"""

# Variáveis comuns obrigatórias (independem do provider)
COMMON_REQUIRED_ENV_VARS = [
    "CLAUDE_CODE_OAUTH_TOKEN",
]


def get_env_template(messaging_provider: str = "telegram") -> str:
    """Gera template de .env combinando tokens comuns + específicos do provider.

    Args:
        messaging_provider: Nome do provider de mensageria.

    Returns:
        Template completo de .env com placeholders.
    """
    parts = [COMMON_ENV_TEMPLATE]

    # Tenta obter template do provider via registry
    try:
        from src.messaging.registry import get as get_provider
        from src.messaging.registry import load_builtin_providers

        load_builtin_providers()
        provider_cls = get_provider(messaging_provider)
        provider_template = provider_cls.env_template()
        if provider_template:
            parts.append(f"# === {messaging_provider.upper()} ===\n\n{provider_template}\n")
    except (ValueError, ImportError):
        # Provider não encontrado — inclui template genérico
        parts.append(f"# Provider '{messaging_provider}' não encontrado — configure manualmente\n")

    parts.append(OPTIONAL_ENV_TEMPLATE)
    return "".join(parts)
