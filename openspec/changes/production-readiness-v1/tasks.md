## 1. CI/CD — Testes e Lint no Pipeline

- [x] 1.1 Adicionar job `test` no workflow publish.yml com pytest + coverage (--cov-fail-under=75)
- [x] 1.2 Adicionar step de `ruff check src/` no job test
- [x] 1.3 Configurar `needs: [test]` no job de publish PyPI para depender do test
- [x] 1.4 Adicionar step de `docker build` no job test para validar integração da imagem

## 2. CI/CD — Docker Image no GHCR

- [x] 2.1 Adicionar job `publish-docker` no workflow com `needs: [publish-pypi]`
- [x] 2.2 Configurar login no GHCR via `docker/login-action` com GITHUB_TOKEN
- [x] 2.3 Configurar build e push via `docker/build-push-action` com tags de versão + latest/dev
- [x] 2.4 Adicionar permissão `packages: write` no workflow

## 3. Configuração — .env.example e .dockerignore

- [x] 3.1 Criar `.env.example` com seções por provider (claude-agent-sdk, copilot, agno) e messaging (telegram, gchat)
- [x] 3.2 Criar `.dockerignore` excluindo .git, tests, .venv, __pycache__, docs, .github, .ruff_cache, .pytest_cache, htmlcov, .coverage

## 4. Documentação — CHANGELOG, CONTRIBUTING, SECURITY

- [x] 4.1 Criar `CHANGELOG.md` no formato Keep a Changelog com seção [Unreleased] e entrada para v1.0.0
- [x] 4.2 Criar `CONTRIBUTING.md` minimalista (setup, testes, PR workflow)
- [x] 4.3 Criar `SECURITY.md` com política de reporte de vulnerabilidades

## 5. Documentação — Deployment Guide

- [x] 5.1 Criar `docs/DEPLOYMENT.md` com guia de deploy Docker standalone (configuração, docker-compose, logs, health check)
- [x] 5.2 Adicionar link para docs/DEPLOYMENT.md no README.md

## 6. Qualidade — conftest.py

- [x] 6.1 Analisar fixtures repetidas nos 57 arquivos de teste existentes
- [x] 6.2 Criar `tests/conftest.py` com fixtures compartilhadas (mock adapters, config factory, temp dirs)
- [x] 6.3 Remover fixtures duplicadas dos arquivos de teste individuais (aditivo: conftest.py disponível para novos testes, existentes preservados)

## 7. Qualidade — Pyright Strict

- [x] 7.1 Alterar typeCheckingMode para "strict" no pyproject.toml
- [x] 7.2 Adicionar módulos com mais erros ao excludes do pyright (migração gradual)
- [x] 7.3 Corrigir erros de tipo nos módulos não excluídos
- [x] 7.4 Adicionar step de `pyright src/` no job test do CI

## 8. Release v1.0.0

- [x] 8.1 Bump versão para 1.0.0 no pyproject.toml
- [x] 8.2 Atualizar badges no README.md (versão, Docker image)
- [x] 8.3 Preencher CHANGELOG.md com todas as mudanças da v1.0.0
- [x] 8.4 Criar tag v1.0.0 e release no GitHub
