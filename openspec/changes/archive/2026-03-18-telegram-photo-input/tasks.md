# Tasks: telegram-photo-input

## Telegram handler

- [x] Adicionar handler para `filters.PHOTO` no TelegramMessageBus (receive_message)
- [x] Baixar foto em maior resolução via `update.message.photo[-1].get_file()`
- [x] Salvar em arquivo temporário `/tmp/telegram_photo_<timestamp>.jpg`
- [x] Extrair caption (ou usar "Analise esta imagem" como fallback)
- [x] Encaminhar callback com texto + image_path

## Daemon

- [x] Adaptar `_handle_new_demand` para aceitar image_path opcional
- [x] Passar image_path ao `run_squad_lead`

## Engine

- [x] Adicionar parâmetro `image_path: str | None = None` ao `run_squad_lead`
- [x] Incluir image_path no context passado ao adapter

## Adapter

- [x] Quando context tem image_path, ler imagem e converter para base64
- [x] Montar prompt como content blocks multimodal (image + text)
- [x] Deletar arquivo temporário após leitura

## Testes

- [x] Teste: handler de foto registrado no Telegram
- [x] Teste: daemon repassa image_path ao engine
- [x] Teste: adapter monta content blocks quando tem imagem
- [x] Teste: adapter mantém texto simples quando não tem imagem
