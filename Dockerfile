# Dockerfile base para execução de agentes em isolamento
FROM python:3.11-slim

# Evita prompts interativos
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cria usuário não-root para execução segura
RUN useradd --create-home --shell /bin/bash agent
WORKDIR /home/agent/workspace

# Copia e instala dependências Python
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir pyyaml pytest pytest-cov pytest-asyncio

# Copia código fonte
COPY src/ src/
COPY platform.yaml .
COPY registry.yaml .

# Restringe permissões
RUN chown -R agent:agent /home/agent
USER agent

# Ponto de entrada padrão
ENTRYPOINT ["python", "-m"]
CMD ["pytest"]
