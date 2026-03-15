# Dockerfile para ai-dev-team (dev mode — usa código-fonte local)
# IMPORTANTE: Claude Code não roda como root

FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    gnupg \
    ca-certificates \
    openssh-client \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Node.js 20 (para claude CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI (para docker.sock do host)
RUN curl -fsSL https://download.docker.com/linux/debian/gpg \
    | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bookworm stable" \
    | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Claude CLI via npm
RUN npm install -g @anthropic-ai/claude-code

# Cria usuário não-root (Claude Code exige isso)
RUN useradd --create-home --shell /bin/bash --uid 1000 agent \
    && usermod -aG sudo agent \
    && echo "agent ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

WORKDIR /app

# Copia e instala dependências Python
COPY pyproject.toml .
COPY src/ src/
COPY agents/ agents/
COPY registry.yaml .

RUN pip install --no-cache-dir .

# Configura diretórios com permissão para o usuário agent
RUN mkdir -p /app/state /workspace /home/agent/.claude \
    && chown -R agent:agent /app /workspace /home/agent

# Troca para usuário não-root
USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD test -f /tmp/ai-dev-team-healthy || exit 1

ENTRYPOINT ["python", "-m", "src.daemon"]
