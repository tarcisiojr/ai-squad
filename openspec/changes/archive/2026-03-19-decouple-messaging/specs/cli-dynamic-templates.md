# Spec: CLI com Templates Dinâmicos

## Requisitos

### REQ-1: Seleção de provider na criação do time
- `ai-squad create MeuTime` pergunta qual messaging provider (default: telegram)
- `ai-squad create MeuTime --messaging gchat` seleciona direto
- Provider escolhido é salvo no `config.yaml`

### REQ-2: Template de .env por provider
- `.env` gerado contém apenas tokens do provider selecionado + tokens comuns (CLAUDE, GITHUB)
- Cada provider define seu template via `env_template()`
- Tokens comuns ficam separados dos específicos do provider

### REQ-3: Validação de tokens por provider
- `validate_required_tokens()` consulta o provider ativo para saber quais tokens validar
- `REQUIRED_ENV_VARS` em `config.py` fica genérico (só tokens comuns)
- Tokens do provider vêm de `required_env_vars()`

## Cenários

### Cenário 1: Criar time com GChat
- Dado comando `ai-squad create MeuTime --messaging gchat`
- Quando CLI gera os arquivos
- Então `config.yaml` tem `messaging_provider: gchat`
- E `.env` tem `GCHAT_CREDENTIALS_PATH` e `GCHAT_SPACE_ID` (não TELEGRAM_*)

### Cenário 2: Criar time sem flag (default Telegram)
- Dado comando `ai-squad create MeuTime`
- Quando CLI gera os arquivos
- Então `config.yaml` tem `messaging_provider: telegram`
- E `.env` tem `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID`
