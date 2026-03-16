## ADDED Requirements

### Requirement: Imagem Docker com todas as dependências
O sistema SHALL fornecer uma imagem Docker que contenha todas as ferramentas necessárias para os agentes operarem.

#### Scenario: Ferramentas disponíveis no container
- **WHEN** o container é iniciado
- **THEN** o container MUST ter disponível: Python 3.11+, Node.js 20+, claude CLI, git, gh CLI, docker CLI e docker-compose

### Requirement: Docker-compose template por time
O sistema SHALL gerar um `docker-compose.yml` funcional para cada time no momento do create.

#### Scenario: Compose com volumes corretos
- **WHEN** o docker-compose é gerado para um time com repo em `/home/user/app`
- **THEN** o compose MUST montar:
  - `/home/user/app:/workspace` (repo alvo, rw)
  - `/var/run/docker.sock:/var/run/docker.sock` (docker engine do host)
  - `./state:/app/state` (persistência de estado)

#### Scenario: Compose com variáveis de ambiente
- **WHEN** o docker-compose é gerado
- **THEN** o compose MUST referenciar variáveis do .env: CLAUDE_CODE_OAUTH_TOKEN, GITHUB_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, e OPENAI_API_KEY

#### Scenario: Container reinicia automaticamente
- **WHEN** o container falha ou o host reinicia
- **THEN** o compose MUST ter `restart: unless-stopped` configurado

### Requirement: Container nome único por time
O sistema SHALL garantir que cada time tenha um container com nome único e previsível.

#### Scenario: Naming convention
- **WHEN** o time se chama `backend-api`
- **THEN** o container MUST ter nome `adt-backend-api`

### Requirement: Limites de recursos
O sistema SHALL definir limites padrão de recursos por container.

#### Scenario: Defaults de recursos
- **WHEN** o docker-compose é gerado
- **THEN** o compose MUST definir limits de memória (2GB) e CPUs (2.0) como defaults

### Requirement: Agentes podem subir infra do projeto
Os agentes dentro do container SHALL conseguir executar comandos Docker para subir infraestrutura do projeto alvo.

#### Scenario: Docker-compose do projeto alvo
- **WHEN** o agente dev precisa subir banco de dados para testar
- **THEN** o agente MUST conseguir executar `docker-compose up -d postgres` dentro de `/workspace` e os containers de infra MUST ser acessíveis pela rede Docker

### Requirement: Build da imagem
O CLI SHALL fornecer mecanismo para construir a imagem Docker.

#### Scenario: Build automático no primeiro start
- **WHEN** o usuário executa start e a imagem `ai-dev-team:latest` não existe
- **THEN** o sistema MUST construir a imagem automaticamente antes de iniciar

#### Scenario: Rebuild manual
- **WHEN** o usuário executa `ai-dev-team build`
- **THEN** o sistema MUST reconstruir a imagem `ai-dev-team:latest`
