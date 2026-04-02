# Guia de Deploy — Docker Standalone

## Pré-requisitos

- Docker 24+ com Docker Compose plugin
- Tokens de API configurados (ver `.env.example`)

## 1. Configuração

```bash
# Crie o time
ai-squad create MeuTime --repo ~/meu-projeto

# Configure as variáveis de ambiente
cd ~/.ai-squad/teams/MeuTime
cp /path/to/ai-squad/.env.example .env
nano .env  # preencha os tokens
```

## 2. Subindo com Docker Compose

O `ai-squad start` gera o `docker-compose.yml` automaticamente:

```bash
ai-squad start MeuTime --docker
```

Ou manualmente com o compose gerado:

```bash
cd ~/.ai-squad/teams/MeuTime
docker compose up -d
```

## 3. Verificando o Status

```bash
# Logs do container
docker compose logs -f ai-squad-MeuTime

# Health check
docker inspect --format='{{.State.Health.Status}}' adt-MeuTime

# Status das demandas
ai-squad status MeuTime
```

O health check usa o arquivo `/tmp/ai-squad-healthy` dentro do container, verificado a cada 30 segundos.

## 4. Parando o Time

```bash
ai-squad stop MeuTime

# Ou diretamente
docker compose down
```

## 5. Atualizando

```bash
# Puxa a imagem mais recente do GHCR
docker pull ghcr.io/tarcisiojr/ai-squad:latest

# Recria o container
ai-squad stop MeuTime
ai-squad start MeuTime --docker
```

## 6. Volumes e Persistência

| Volume | Caminho no Container | Descrição |
|--------|---------------------|-----------|
| Repositório | `/workspace` | Código-fonte do projeto alvo |
| Estado | `/app/state` | Persistência de pipeline, journal, conversas |
| Config | `/app/config.yaml` | Configuração do time (read-only) |
| Agentes | `/app/agents` | AGENTS.md e skills customizados (read-only) |
| Pipeline | `/app/pipeline` | Pipeline YAML e steps (read-only) |
| SSH | `/home/agent/.ssh` | Chaves SSH do host (read-only) |
| Git | `/home/agent/.gitconfig` | Config git do host (read-only) |

## 7. Recursos

O container tem limites padrão de:
- **2 GB RAM** / **2 CPUs** para o ai-squad
- **4 GB RAM** / **4 CPUs** para o Whisper (transcrição de voz)

Para ajustar, edite o `docker-compose.yml` gerado na seção `deploy.resources.limits`.

## 8. Troubleshooting

**Container reiniciando em loop:**
- Verifique os logs: `docker compose logs ai-squad-MeuTime`
- Confirme que `.env` tem os tokens preenchidos (sem `PREENCHA_AQUI_`)

**Health check failing:**
- O arquivo `/tmp/ai-squad-healthy` é criado após o daemon inicializar
- Start period é de 10 segundos — aguarde antes de verificar

**Permissão negada no repositório:**
- O container roda como usuário `agent` (uid 1000)
- Verifique que o diretório do repositório tem permissão para uid 1000
