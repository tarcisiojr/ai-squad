## ADDED Requirements

### Requirement: .env.example como referência de configuração
O projeto SHALL ter um arquivo `.env.example` na raiz com todas as variáveis de ambiente organizadas por provider, com valores placeholder e comentários explicativos.

#### Scenario: Variáveis do provider claude-agent-sdk
- **WHEN** um usuário configura o provider claude-agent-sdk
- **THEN** encontra no .env.example as variáveis: `CLAUDE_CODE_OAUTH_TOKEN`, `GITHUB_TOKEN` (opcional), `OPENAI_API_KEY` (opcional para Whisper)

#### Scenario: Variáveis do provider agno
- **WHEN** um usuário configura o provider agno
- **THEN** encontra no .env.example a variável `GOOGLE_API_KEY` com comentário indicando que é obrigatória para este provider

#### Scenario: Variáveis de messaging telegram
- **WHEN** um usuário configura messaging via telegram
- **THEN** encontra no .env.example as variáveis `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`

#### Scenario: Seções com comentários explicativos
- **WHEN** um usuário abre o .env.example
- **THEN** cada seção tem um comentário de cabeçalho indicando o provider e quais variáveis são obrigatórias vs opcionais
