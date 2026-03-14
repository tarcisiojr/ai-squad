## ADDED Requirements

### Requirement: Arquivo centralizado platform.yaml
O sistema SHALL usar `platform.yaml` como arquivo único de configuração para: `ai_provider` (provider de IA), `messaging_provider` (provider de mensageria), parâmetros globais e configurações por persona.

#### Scenario: Carregamento de configuração
- **WHEN** a plataforma inicia
- **THEN** platform.yaml é carregado e validado antes de qualquer componente ser instanciado

#### Scenario: Configuração inválida rejeitada
- **WHEN** platform.yaml contém um `ai_provider` não registrado
- **THEN** o sistema emite erro claro e recusa iniciar

### Requirement: Troca de provider sem alteração de código
Trocar provider de IA SHALL exigir apenas alteração do campo `ai_provider` no `platform.yaml`. Trocar provider de mensageria SHALL exigir apenas alteração do campo `messaging_provider`.

#### Scenario: Migração de Telegram para Slack
- **WHEN** `messaging_provider` é alterado de `telegram` para `slack`
- **THEN** o sistema utiliza `SlackMessageBus` sem nenhuma alteração de código

### Requirement: Configuração por persona
O platform.yaml SHALL suportar configuração específica por persona (PO, Dev, QA), incluindo: tokens de bot, nomes de exibição e avatares.

#### Scenario: Tokens separados por persona
- **WHEN** a configuração inclui tokens distintos para PO, Dev e QA
- **THEN** cada persona utiliza seu próprio token ao interagir via barramento
