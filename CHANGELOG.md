# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

## [1.0.0] - 2026-04-01

### Added
- Pipeline CI/CD completo com testes, lint e coverage antes do publish
- Imagem Docker oficial publicada no GHCR (ghcr.io)
- `.env.example` com todas as variáveis de ambiente por provider
- `.dockerignore` para otimizar tamanho da imagem Docker
- `CONTRIBUTING.md` com guia de contribuição
- `SECURITY.md` com política de reporte de vulnerabilidades
- `docs/DEPLOYMENT.md` com guia de deploy Docker standalone
- `tests/conftest.py` com fixtures compartilhadas
- Validação de Docker build no CI
- Pyright strict mode (migração gradual)

### Changed
- Workflow CI/CD reestruturado com jobs separados: test → publish-pypi → publish-docker
- Type checking atualizado de basic para strict no pyright
- Badge de versão e Docker image no README

[Unreleased]: https://github.com/tarcisiojr/ai-squad/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/tarcisiojr/ai-squad/releases/tag/v1.0.0
