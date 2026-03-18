## Context

O TelegramMessageBus já tem handlers para texto e voz. A API do python-telegram-bot suporta download de fotos via `update.message.photo[-1].get_file()`. O Claude Agent SDK aceita imagens no prompt via content blocks multimodal.

## Goals / Non-Goals

**Goals:**
- Usuário envia foto no Telegram → Squad Lead recebe e analisa
- Caption da foto é usada como texto da mensagem
- Sem caption, usa texto genérico "Analise esta imagem"
- Imagem salva em /tmp/ e caminho passado ao engine

**Non-Goals:**
- Vídeos, documentos, stickers
- Múltiplas fotos por mensagem
- Persistência de imagens (temporárias em /tmp/)

## Decisions

### 1. Download via python-telegram-bot API

**Decisão:** Usar `update.message.photo[-1].get_file()` para pegar a maior resolução e `file.download_to_drive()` para salvar.

**Justificativa:** API nativa do python-telegram-bot, sem dependências extras.

### 2. Caminho da imagem como parâmetro opcional

**Decisão:** Adicionar parâmetro `image_path: str | None` no fluxo mensagem → daemon → engine → adapter.

**Alternativa considerada:** Salvar imagem e referenciar no texto (ex: "[imagem: /tmp/foto.jpg]"). Rejeitada porque o Claude SDK suporta content blocks multimodal nativamente — melhor passar a imagem diretamente.

### 3. Content block multimodal no adapter

**Decisão:** Quando `image_path` está presente, o adapter monta o prompt como lista de content blocks:
```python
[
    {"type": "image", "source": {"type": "base64", "data": "..."}},
    {"type": "text", "text": "prompt textual"}
]
```

**Justificativa:** Formato nativo da API Claude para visão multimodal.

## Risks / Trade-offs

- **[Risco] Imagem muito grande** → Mitigação: Telegram já comprime fotos; usar maior resolução disponível mas não o arquivo original
- **[Risco] /tmp/ enche com imagens** → Mitigação: deletar imagem após enviar ao adapter
- **[Trade-off] Apenas primeira foto** → Aceito por simplicidade; pode expandir depois
