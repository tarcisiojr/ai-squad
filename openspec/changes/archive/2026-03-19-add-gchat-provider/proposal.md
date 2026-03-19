# Proposal: add-gchat-provider

## Problema

A plataforma só suporta Telegram e CLI como canais de mensageria. O desacoplamento (change decouple-messaging) preparou a arquitetura para novos providers, mas nenhum foi implementado ainda. O Google Chat é o IM principal da empresa do usuário.

## Solução

Implementar `GChatMessageBus` como novo provider de mensageria:

- **Auth**: Service Account (bot headless)
- **Recebimento**: Polling via `spaces.messages.list()` (simples, zero infra extra)
- **Envio**: `spaces.messages.create()` com texto e Cards v2
- **Aprovações**: Cards v2 com botões (action callbacks)
- **Threads**: `thread.threadKey` para isolamento de demandas em Spaces
- **Dependências**: `google-auth`, `google-api-python-client`

## Escopo

### Incluso
- `src/messaging/gchat.py` — implementação completa do GChatMessageBus
- Auto-registro no registry
- Polling loop assíncrono para receber mensagens
- Cards v2 para aprovações com botões
- Suporte a threads em Spaces
- Testes unitários
- Documentação de env vars e setup

### Excluído
- Voice/transcrição (fica para depois)
- Pub/Sub (polling é suficiente por agora)
- Upload de fotos/documentos (GChat usa Drive links — complexo)
- Reações
