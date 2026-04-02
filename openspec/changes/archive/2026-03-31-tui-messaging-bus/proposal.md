# TUI Messaging Bus

## Problema

O ai-squad hoje depende de Telegram ou Google Chat para interação. O CLIMessageBus existente é um stub (print/input) sem experiência real de chat — não tem input loop, não mostra personas, não suporta interação assíncrona com agentes rodando em background.

Desenvolvedores que querem testar localmente ou usar o squad sem configurar serviços externos não têm uma experiência funcional.

## Proposta

Implementar um `TUIMessageBus` usando [Textual](https://textual.textualize.io/) como novo provider de mensageria. A experiência será um chat interativo no terminal com:

- Chat com scroll e mensagens identificadas por persona (avatar + nome)
- Input assíncrono integrado ao daemon (asyncio)
- Streaming de progresso dos agentes via `report_progress`
- Comandos `/help`, `/status`, `/stop`, `/skills`
- Compatível com o fluxo completo do daemon (Squad Lead + agentes)

## Escopo

### Inclui (v1)
- `TUIMessageBus` implementando `MessageBus` ABC
- App Textual com chat panel + input widget
- Registro como provider `tui` no registry
- Dependência opcional `[tui]` no pyproject.toml
- Ativação via `messaging_provider: tui` ou flag `--tui`

### Não inclui (futuro)
- Painel lateral de status dos agentes
- Painel de pipeline
- Multi-painel por thread/demanda
- Temas/customização visual

## Motivação

- Desenvolvimento local sem dependências externas
- Testes de integração mais realistas que o CLI stub
- Experiência de primeira classe para devs que preferem terminal
