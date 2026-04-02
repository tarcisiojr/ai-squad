## Context

O AI Squad v0.2.4 publica no PyPI via GitHub Actions mas o workflow não executa testes antes do publish. A imagem Docker existe como Dockerfile no repo mas não é publicada em nenhum registry. Documentação de operação (deploy, contribuição, changelog) está ausente. O type checking usa modo basic do pyright e os 57 arquivos de teste não compartilham fixtures.

O projeto tem uma base sólida: 446+ testes, 75%+ coverage, graceful shutdown, retry com backoff, config 12-factor. O gap é exclusivamente de tooling, CI/CD e documentação.

## Goals / Non-Goals

**Goals:**
- CI/CD que garanta: testes passam → lint passa → build → publish PyPI → build e push Docker image GHCR
- Documentação suficiente para um desenvolvedor novo configurar, rodar e contribuir
- Imagem Docker oficial disponível no GHCR
- Qualidade de código reforçada (conftest.py, pyright strict)
- Tag v1.0.0 como marco de estabilidade

**Non-Goals:**
- Health check HTTP (escopo K8s futuro)
- Schema versioning para state/FTS5 (pós v1.0.0)
- Publicação no Docker Hub (segundo registry, futuro)
- Reescrever testes existentes
- Mudar arquitetura ou funcionalidades do core

## Decisions

### D1: Registry Docker — GHCR
**Escolha:** GitHub Container Registry (ghcr.io)
**Alternativas:** Docker Hub, AWS ECR
**Racional:** Integração nativa com GitHub Actions, mesmo OIDC token do PyPI publish, sem conta adicional. Docker Hub será adicionado no futuro como segundo registry.

### D2: Workflow CI único com jobs separados
**Escolha:** Um workflow com jobs: `test` → `publish-pypi` → `publish-docker`, usando `needs` para dependência
**Alternativas:** Workflows separados, job único monolítico
**Racional:** Jobs separados permitem paralelismo onde possível e falha independente. Um único workflow mantém a visibilidade. O job `test` bloqueia os demais.

### D3: conftest.py na raiz de tests/
**Escolha:** Um único `tests/conftest.py` com fixtures comuns (mock adapters, config factory, temp dirs)
**Alternativas:** conftest.py por subdiretório, sem conftest
**Racional:** Um arquivo central é suficiente para o tamanho atual do projeto. Fixtures específicas podem ficar nos conftest dos subdiretórios se necessário no futuro.

### D4: Pyright strict — migração gradual
**Escolha:** Ativar strict mode e adicionar exceções por módulo no pyproject.toml até corrigir todos
**Alternativas:** Migrar tudo de uma vez, manter basic
**Racional:** Strict mode de uma vez geraria centenas de erros. Migração gradual permite corrigir módulo a módulo sem bloquear o v1.0.0.

### D5: .env.example organizado por provider
**Escolha:** Seções comentadas por provider com valores placeholder
**Alternativas:** Arquivo único sem seções, múltiplos .env por provider
**Racional:** Um único arquivo com seções é fácil de copiar e entender. Comentários explicam quando cada variável é necessária.

### D6: CHANGELOG formato Keep a Changelog
**Escolha:** Formato [Keep a Changelog](https://keepachangelog.com/) com categorias Added/Changed/Fixed/Removed
**Alternativas:** Formato livre, conventional commits auto-generated
**Racional:** Padrão reconhecido, fácil de manter manualmente, não requer tooling adicional.

## Risks / Trade-offs

- **[Pyright strict gera muitos erros]** → Migração gradual com excludes por módulo. Não bloqueia v1.0.0 se alguns módulos ainda estiverem em basic.
- **[GHCR image grande]** → .dockerignore exclui .git, tests, .venv, docs. Dockerfile existente já usa multi-layer.
- **[CI mais lento]** → Testes adicionam ~2-3min ao pipeline. Aceitável para a segurança que trazem.
- **[conftest.py pode conflitar com fixtures inline]** → Revisar fixtures existentes antes de centralizar. Manter apenas as verdadeiramente comuns.
