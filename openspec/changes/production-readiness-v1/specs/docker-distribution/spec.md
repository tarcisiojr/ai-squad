## ADDED Requirements

### Requirement: Imagem Docker publicada no GHCR
O projeto SHALL publicar uma imagem Docker oficial no GitHub Container Registry (ghcr.io) a cada release e push para main.

#### Scenario: Imagem taggeada com versão
- **WHEN** uma release é publicada (tag vX.Y.Z)
- **THEN** a imagem é publicada no GHCR com tag da versão (ex: ghcr.io/tarcisiojr/ai-squad:1.0.0) e tag `latest`

#### Scenario: Imagem dev em push para main
- **WHEN** um push é feito para main (sem tag de release)
- **THEN** a imagem é publicada com tag `dev` (ex: ghcr.io/tarcisiojr/ai-squad:dev)

### Requirement: .dockerignore para imagem otimizada
O projeto SHALL ter um arquivo `.dockerignore` na raiz que exclui arquivos desnecessários para reduzir o tamanho da imagem.

#### Scenario: Arquivos excluídos da imagem
- **WHEN** o Docker build é executado
- **THEN** os seguintes são excluídos: `.git/`, `tests/`, `.venv/`, `__pycache__/`, `*.pyc`, `.coverage`, `htmlcov/`, `.pytest_cache/`, `docs/`, `.github/`, `.ruff_cache/`
