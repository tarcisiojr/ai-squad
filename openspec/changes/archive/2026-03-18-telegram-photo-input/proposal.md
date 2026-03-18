# Proposal: Suporte a fotos via Telegram

## Why

Hoje o Telegram handler escuta apenas texto, comandos e áudio. Quando o usuário envia uma foto, ela é ignorada silenciosamente. O Claude suporta visão multimodal — consegue analisar imagens se receber o arquivo. Isso é útil para: enviar screenshots de bugs, layouts de referência, diagramas, ou qualquer contexto visual.

## What Changes

### Handler de fotos no Telegram
- Adicionar handler para `filters.PHOTO` no TelegramMessageBus
- Baixar a imagem via API do Telegram e salvar em arquivo temporário
- Encaminhar ao Squad Lead junto com a caption (se houver)

### Passagem de imagem ao engine
- O engine recebe o caminho da imagem junto com o texto
- O adapter passa a imagem como contexto multimodal ao Claude Agent SDK

## Capabilities

### telegram-photo-handler
Receber fotos enviadas pelo usuário no Telegram, baixar e encaminhar ao engine.

### image-context
Passar imagens como contexto multimodal ao Squad Lead e agentes via Claude Agent SDK.

## Impact

### Arquivos modificados
- `src/messaging/telegram.py` — novo handler para PHOTO, download da imagem
- `src/messaging/interface.py` — callback de mensagem aceita imagem opcional
- `src/daemon.py` — recebe e repassa imagem ao engine
- `src/orchestrator/engine.py` — aceita imagem no run_squad_lead
- `src/adapters/claude_agent_sdk.py` — passa imagem no prompt multimodal

### Sem impacto
- CLI, presets, pipeline, orchestrator (exceto engine)
- Modo local vs Docker — funciona em ambos

## Non-Goals
- Envio de vídeos ou documentos (apenas fotos)
- Processamento de múltiplas fotos em uma mensagem (apenas a primeira)
- OCR dedicado — o Claude faz nativamente via visão
