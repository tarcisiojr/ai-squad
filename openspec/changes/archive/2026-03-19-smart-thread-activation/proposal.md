## Why

Quando o bot é adicionado a um espaço/grupo (GChat ou Telegram), ele responde a TODAS as mensagens — mesmo quando um humano já está resolvendo o problema. Isso é disruptivo em cenários de time de apoio onde threads são usadas como unidade de incidente e múltiplas pessoas (humanas e bot) podem atuar simultaneamente. Nenhuma ferramenta séria do mercado (Copilot, Slack agents, Google Chat nativo) responde a tudo em grupo por default — o padrão é mention-based.

## What Changes

- Novo `activation_mode` configurável no `config.yaml`: `mention`, `all` ou `command` — controla quando o bot responde em espaços/grupos (DM sempre é `all`)
- Novo componente `ThreadTracker` que gerencia o estado do bot por thread: `active` (lidera), `standby` (humano assumiu) e `convocado` (responde pontualmente a @mention)
- Quando um humano responde numa thread onde o bot está ativo, o bot recua automaticamente para standby e avisa
- O bot pode ser re-convocado a qualquer momento via @mention, inclusive para registrar aprendizados ao final de um incidente
- Timeout configurável: se humano assumiu mas ficou inativo por X minutos, bot oferece ajuda novamente
- Estado das threads persistido em `state/` via escrita atômica (sobrevive a restarts)
- Tempos configuráveis com valores default sensatos

## Capabilities

### New Capabilities
- `activation-mode`: Filtro de ativação configurável (mention/all/command) na camada de messaging, com comportamento diferenciado para DM vs grupo
- `thread-tracker`: Componente de rastreamento de estado por thread (active/standby/convocado) com persistência, transições automáticas e timeouts configuráveis

### Modified Capabilities
- `messaging-bus`: Interface do MessageBus precisa expor informações de menção e tipo de chat (DM vs grupo) para que o filtro de ativação funcione

## Impact

- **Messaging layer**: `src/messaging/interface.py` (novos métodos), `src/messaging/gchat.py` e `src/messaging/telegram.py` (filtro de menção)
- **Novo componente**: `src/orchestrator/thread_tracker.py`
- **Config**: Novos campos `activation_mode` e `thread_tracking` no `config.yaml`
- **Daemon**: `src/daemon.py` — integração com ThreadTracker antes de processar mensagens
- **State**: Novo arquivo `state/threads.json` para persistência
