## 1. CopilotGenerator

- [x] 1.1 Criar `src/cli/generators/copilot.py` com classe `CopilotGenerator` herdando `GeneratorProvider`
- [x] 1.2 Implementar `generate(prompt)` usando `CopilotClient` do copilot-sdk (async com `asyncio.run`)
- [x] 1.3 Tratar `ImportError` do copilot-sdk com mensagem: "Instale com: pip install -e '.[copilot]'"
- [x] 1.4 Tratar erro de auth não configurada com mensagem orientando `copilot auth login`

## 2. Registro do Provider

- [x] 2.1 Adicionar `"copilot"` em `PROVIDER_CONFIGS` no `src/cli/generators/interface.py` com `ai_provider="copilot"`, `env_var=""`, `default_model=""`
- [x] 2.2 Adicionar branch `"copilot"` no `get_provider()` retornando `CopilotGenerator`

## 3. Wizard Interativo

- [x] 3.1 Adicionar `"copilot"` na lista de choices do `_ask_provider()` em `src/cli/wizard.py`
- [x] 3.2 Modificar `_ask_token()` para pular ou tornar opcional quando provider é "copilot", informando sobre auth via CLI
- [x] 3.3 Garantir que `WizardResult.token` aceita string vazia para copilot

## 4. Geração de Config/Env

- [x] 4.1 Verificar que `generate_team()` em `src/cli/generate.py` lida com token vazio (copilot) sem gerar placeholder no .env
- [x] 4.2 Verificar que `get_env_template()` em `src/cli/templates/config.py` já trata copilot (COPILOT_ENV_TEMPLATE)

## 5. Testes

- [x] 5.1 Criar testes unitários para `CopilotGenerator` (mock do copilot-sdk)
- [x] 5.2 Criar testes para o registro do provider copilot em interface.py
- [x] 5.3 Criar testes para o wizard com provider copilot (token opcional)
