## Why

O AI Squad está funcional em v0.2.4 (Beta) mas o pipeline de CI/CD publica no PyPI sem rodar testes, não há imagem Docker oficial, e faltam documentos essenciais (.env.example, CHANGELOG, CONTRIBUTING, guia de deploy) para que outros possam reproduzir e contribuir. Precisamos fechar esses gaps para alcançar uma v1.0.0 confiável e pronta para produção.

## What Changes

- **CI/CD reforçado**: Adicionar steps de pytest + ruff check antes do publish no PyPI; adicionar build e push de imagem Docker no GHCR
- **`.env.example`**: Template com todas as variáveis de ambiente por provider (claude-agent-sdk, copilot, agno, telegram, gchat)
- **`.dockerignore`**: Excluir arquivos desnecessários da imagem Docker
- **`CHANGELOG.md`**: Histórico de mudanças a partir da versão atual
- **`CONTRIBUTING.md`**: Guia minimalista (setup, testes, PR workflow)
- **`SECURITY.md`**: Política de reporte de vulnerabilidades
- **`docs/DEPLOYMENT.md`**: Guia de deploy Docker standalone com link no README
- **`conftest.py`**: Fixtures compartilhadas para os 57 arquivos de teste
- **Pyright strict mode**: Upgrade gradual do type checking de basic para strict
- **Teste de integração Docker**: Validar que o build da imagem funciona no CI
- **Bump para v1.0.0**: Atualizar versão no pyproject.toml e criar tag

## Capabilities

### New Capabilities
- `ci-pipeline`: Pipeline CI/CD completo com testes, lint, build Docker e publish (PyPI + GHCR)
- `production-docs`: Documentação de produção (CHANGELOG, CONTRIBUTING, SECURITY, DEPLOYMENT)
- `docker-distribution`: Imagem Docker oficial publicada no GHCR

### Modified Capabilities
- `platform-config`: Adição de `.env.example` como referência de configuração

## Impact

- `.github/workflows/publish.yml` — reestruturação completa do workflow
- `pyproject.toml` — bump de versão para 1.0.0, possível ajuste de pyright config
- `tests/conftest.py` — novo arquivo com fixtures compartilhadas
- `README.md` — adição de link para docs/DEPLOYMENT.md e badges atualizados
- Raiz do projeto — novos arquivos: `.env.example`, `.dockerignore`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`
- `docs/` — novo arquivo: `DEPLOYMENT.md`
