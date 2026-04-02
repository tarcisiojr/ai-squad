## ADDED Requirements

### Requirement: CHANGELOG em formato Keep a Changelog
O projeto SHALL manter um arquivo `CHANGELOG.md` na raiz seguindo o formato Keep a Changelog, com categorias Added, Changed, Fixed, Removed por versão.

#### Scenario: Nova versão documentada
- **WHEN** uma nova versão é preparada para release
- **THEN** o CHANGELOG.md contém uma seção com o número da versão, data e categorias de mudanças

#### Scenario: Seção Unreleased para trabalho em progresso
- **WHEN** mudanças são feitas entre releases
- **THEN** as mudanças são documentadas na seção [Unreleased] no topo do CHANGELOG

### Requirement: CONTRIBUTING minimalista
O projeto SHALL ter um arquivo `CONTRIBUTING.md` na raiz com instruções de setup do ambiente, como rodar testes e como abrir pull requests.

#### Scenario: Desenvolvedor novo configura ambiente
- **WHEN** um novo contribuidor lê CONTRIBUTING.md
- **THEN** encontra instruções para: clonar o repo, criar virtualenv, instalar dependências e rodar testes

#### Scenario: PR workflow documentado
- **WHEN** um contribuidor quer abrir um PR
- **THEN** encontra instruções sobre branch naming, commit messages e checklist de validação

### Requirement: SECURITY.md com política de reporte
O projeto SHALL ter um arquivo `SECURITY.md` na raiz com instruções de como reportar vulnerabilidades de segurança.

#### Scenario: Vulnerabilidade reportada
- **WHEN** alguém descobre uma vulnerabilidade
- **THEN** encontra no SECURITY.md instruções claras de como reportar de forma privada

### Requirement: Guia de deployment
O projeto SHALL ter um arquivo `docs/DEPLOYMENT.md` com instruções de deploy via Docker standalone, e o README MUST conter um link para este guia.

#### Scenario: Operador faz deploy via Docker
- **WHEN** um operador lê docs/DEPLOYMENT.md
- **THEN** encontra instruções completas para: configurar .env, rodar com docker-compose, verificar logs e health check

#### Scenario: README aponta para guia de deploy
- **WHEN** um usuário lê o README.md
- **THEN** encontra um link para docs/DEPLOYMENT.md na seção de documentação
