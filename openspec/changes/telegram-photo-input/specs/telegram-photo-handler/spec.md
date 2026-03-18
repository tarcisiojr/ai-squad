## ADDED Requirements

### Requirement: Telegram recebe fotos do usuário
O TelegramMessageBus SHALL registrar handler para filters.PHOTO e processar fotos enviadas pelo usuário.

#### Scenario: Foto com caption
- **WHEN** usuário envia foto com caption "Esse é o bug"
- **THEN** sistema SHALL baixar a foto em maior resolução
- **THEN** sistema SHALL salvar em arquivo temporário (/tmp/)
- **THEN** sistema SHALL encaminhar ao daemon com texto "Esse é o bug" e caminho da imagem

#### Scenario: Foto sem caption
- **WHEN** usuário envia foto sem caption
- **THEN** sistema SHALL baixar a foto e salvar em /tmp/
- **THEN** sistema SHALL encaminhar ao daemon com texto "Analise esta imagem" e caminho da imagem

#### Scenario: Limpeza após processamento
- **WHEN** foto foi processada e enviada ao engine
- **THEN** arquivo temporário SHALL ser deletado
