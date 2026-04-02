# Contribuindo com o AI Squad

## Setup do Ambiente

```bash
# Clone o repositório
git clone https://github.com/tarcisiojr/ai-squad.git
cd ai-squad

# Crie e ative o virtualenv
python -m venv .venv
source .venv/bin/activate

# Instale com dependências de desenvolvimento
pip install -e ".[dev]"
```

## Rodando Testes

```bash
# Todos os testes com coverage
pytest

# Testes de um módulo específico
pytest tests/orchestrator/

# Lint
ruff check src/

# Type checking
pyright src/
```

O coverage mínimo é **75%**. Testes que reduzem o coverage abaixo desse valor serão rejeitados no CI.

## Abrindo um Pull Request

1. Crie uma branch a partir de `main`: `git checkout -b minha-feature`
2. Faça suas mudanças com commits descritivos
3. Verifique que testes e lint passam localmente
4. Abra o PR descrevendo o que foi feito e por quê
5. Aguarde review

## Convenções

- **Código**: siga o estilo existente (ruff formata automaticamente)
- **Testes**: espelhe a estrutura de `src/` em `tests/`
- **Commits**: mensagens claras e em português ou inglês
- **Documentação**: comentários e docstrings em português
