## Context

O comando `generate` usa providers de IA para gerar pipelines e agentes a partir de uma descrição textual. Atualmente suporta 3 providers (anthropic, openai, agno), todos exigindo token explícito. O Copilot já é suportado como runtime adapter (`src/adapters/copilot_adapter.py`) mas não como generator. A autenticação Copilot é diferente: usa `copilot auth login` (sem token) ou `GITHUB_TOKEN` opcional.

## Goals / Non-Goals

**Goals:**
- Adicionar Copilot como provider no `generate`, seguindo o padrão existente (`GeneratorProvider`)
- Adaptar o wizard para o fluxo de autenticação sem token obrigatório do Copilot
- Produzir config.yaml com `ai_provider: copilot` quando Copilot é o provider de geração

**Non-Goals:**
- Alterar o runtime adapter do Copilot (`copilot_adapter.py`)
- Adicionar novos modelos ao Copilot (usa o default do SDK)
- Mudar o fluxo de outros providers

## Decisions

### 1. CopilotGenerator usa CopilotClient do SDK existente
**Decisão**: Reutilizar o padrão do `copilot_adapter.py` para instanciar `CopilotClient` com `CopilotClientOptions`.

**Alternativa descartada**: Usar API REST do GitHub Copilot diretamente — adicionaria complexidade de autenticação sem benefício, já que o SDK já resolve isso.

**Rationale**: O SDK já lida com auth (GITHUB_TOKEN ou CLI login), session management e model routing.

### 2. Token opcional no wizard para Copilot
**Decisão**: Quando o provider é "copilot", o wizard pula a etapa de token (ou aceita GITHUB_TOKEN opcional). A autenticação primária é via `copilot auth login`.

**Alternativa descartada**: Forçar GITHUB_TOKEN — quebraria o fluxo mais comum de auth via CLI.

**Rationale**: Copilot é o único provider que não exige token explícito. O wizard deve refletir isso.

### 3. ProviderConfig com env_var vazio para Copilot
**Decisão**: `PROVIDER_CONFIGS["copilot"]` usa `env_var=""` (como já feito no `_PROVIDER_AI_TOKENS` do factory.py) e `ai_provider="copilot"`.

**Rationale**: Mantém consistência com o mapeamento existente. O `.env` gerado não terá placeholder de token AI para copilot.

### 4. Modelo default: vazio (usa default do SDK)
**Decisão**: Não fixar modelo no generator — o Copilot SDK usa o modelo disponível na subscription do usuário.

**Rationale**: Diferente de anthropic/openai/agno, o Copilot não permite escolha arbitrária de modelo.

## Risks / Trade-offs

- **[SDK não instalado]** → Mesma mitigação dos outros providers: ImportError com mensagem "Instale com: pip install -e '.[copilot]'"
- **[Auth via CLI pode falhar]** → Se `copilot auth login` não foi feito, o SDK lança erro. Mitigação: catch do erro com mensagem orientando o usuário a rodar `copilot auth login`
- **[Copilot pode ter rate limits diferentes]** → Aceito. O generate faz apenas 1 chamada, improvável atingir limite
