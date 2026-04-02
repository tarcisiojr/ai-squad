## ADDED Requirements

### Requirement: CI executa testes antes do publish
O workflow SHALL executar `pytest` com coverage e `ruff check` antes de qualquer step de publish. Se qualquer teste falhar ou o lint reportar erros, o pipeline MUST falhar e não publicar.

#### Scenario: Testes passam e publish acontece
- **WHEN** push para main e todos os testes passam e ruff check passa
- **THEN** o pipeline avança para os steps de publish (PyPI e Docker)

#### Scenario: Teste falha e bloqueia publish
- **WHEN** push para main e algum teste falha
- **THEN** o pipeline falha no job de test e os jobs de publish NÃO executam

#### Scenario: Lint falha e bloqueia publish
- **WHEN** push para main e ruff check reporta erros
- **THEN** o pipeline falha no job de test e os jobs de publish NÃO executam

### Requirement: CI publica imagem Docker no GHCR
O workflow SHALL buildar a imagem Docker e fazer push para ghcr.io após o publish no PyPI ser bem-sucedido. A imagem MUST ser taggeada com a versão do pacote e `latest`.

#### Scenario: Publish Docker após PyPI com sucesso
- **WHEN** o job de publish PyPI completa com sucesso
- **THEN** o pipeline builda a imagem Docker e faz push para ghcr.io com tags de versão e latest

#### Scenario: PyPI falha e Docker não executa
- **WHEN** o job de publish PyPI falha
- **THEN** o job de publish Docker NÃO executa

### Requirement: CI usa jobs com dependências
O workflow SHALL organizar o pipeline em jobs separados: `test`, `publish-pypi`, `publish-docker`, usando `needs` para definir dependências.

#### Scenario: Ordem de execução dos jobs
- **WHEN** o workflow é disparado
- **THEN** o job `test` executa primeiro, `publish-pypi` executa após `test` passar, e `publish-docker` executa após `publish-pypi` passar

### Requirement: Teste de integração do Docker build
O job de test SHALL incluir um step que valida que o `docker build` completa com sucesso, sem executar o container.

#### Scenario: Docker build validado no CI
- **WHEN** o job de test executa
- **THEN** um step executa `docker build` e verifica que a imagem é criada sem erros
