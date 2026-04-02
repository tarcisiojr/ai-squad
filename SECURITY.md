# Política de Segurança

## Reportando Vulnerabilidades

Se você encontrou uma vulnerabilidade de segurança no AI Squad, **não abra uma issue pública**.

Envie um email para **tarcisiojr@gmail.com** com:

- Descrição da vulnerabilidade
- Passos para reproduzir
- Impacto potencial

Você receberá uma resposta em até **72 horas** com os próximos passos.

## Escopo

Esta política cobre o código do repositório [tarcisiojr/ai-squad](https://github.com/tarcisiojr/ai-squad). Vulnerabilidades em dependências de terceiros devem ser reportadas aos mantenedores dessas dependências.

## Boas Práticas

- Nunca commite secrets, tokens ou API keys no repositório
- Use `.env` para variáveis sensíveis (já incluído no `.gitignore`)
- Consulte `.env.example` para a lista completa de variáveis
