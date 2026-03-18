# Dockerfile para ai-squad (dev mode — usa código-fonte local)
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
    ffmpeg \
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

# Claude CLI, OpenSpec CLI, Playwright CLI, Context Mode e Context7 via npm
RUN npm install -g @anthropic-ai/claude-code @fission-ai/openspec @playwright/cli context-mode @upstash/context7-mcp

# Instala dependencias de sistema do Playwright (precisa ser root)
RUN npx playwright install-deps chromium

# Cria usuário não-root (Claude Code exige isso)
RUN useradd --create-home --shell /bin/bash --uid 1000 agent \
    && usermod -aG sudo agent \
    && echo "agent ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

WORKDIR /app

# Instala pacote Python via .whl (gerado pelo build)
COPY *.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl

# Configura diretórios com permissão para o usuário agent
RUN mkdir -p /app/state /workspace /home/agent/.claude \
    && chown -R agent:agent /app /workspace /home/agent

# Configura MCP servers: context-mode (economia de contexto) + context7 (docs atualizadas)
COPY <<'MCPEOF' /home/agent/.claude/settings.json
{
  "mcpServers": {
    "context-mode": {
      "type": "stdio",
      "command": "context-mode",
      "args": ["--transport", "stdio"]
    },
    "context7": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
MCPEOF
RUN chown agent:agent /home/agent/.claude/settings.json

# Troca para usuário não-root
USER agent

# Instala browser Chromium como usuario agent
RUN npx playwright install chromium

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD test -f /tmp/ai-squad-healthy || exit 1

ENTRYPOINT ["python", "-m", "src.daemon"]
