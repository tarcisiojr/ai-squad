## Why

Hoje todas as mensagens para o Squad Lead caem no mesmo `"squad-lead-session"` — um ID fixo hardcoded no daemon. Isso mistura conversas, journals, pipeline states e históricos de demandas diferentes no mesmo balde. O LLM "chuta" qual demanda o usuário está referenciando, sem nenhum mecanismo determinístico. Com múltiplos usuários no futuro, o problema escala de "confuso" para "inutilizável". Frameworks de referência (OpenClaw, LangGraph, CrewAI) resolvem isso com isolamento estrutural, não inferência — e o Telegram já oferece Forum Topics como primitiva nativa para isso.

## What Changes

- **Suporte a Forum Topics no Telegram** — cada demanda ganha seu próprio tópico no grupo, com isolamento completo de conversa, journal e pipeline state
- **Roteamento por thread_id no daemon** — mensagens em tópicos específicos são roteadas diretamente para o demand_id correspondente; tópico geral serve para conversa livre com o Squad Lead
- **Mapeamento thread_id ↔ demand_id** — novo registro que associa tópicos do Telegram a demandas, persistido em disco
- **Contexto de demanda nos agentes** — respostas de agentes (progresso, resultado, erros) são enviadas ao tópico correto da demanda
- **Separação chat_id vs user_id** — **BREAKING** — handlers passam a distinguir quem mandou (from_user.id) do onde mandou (chat_id), preparando para multi-usuário
- **Fallback para modo flat** — se o chat não for grupo-fórum (ex: DM), comportamento atual é preservado (single-demand)

## Capabilities

### New Capabilities
- `forum-topic-routing`: Criação automática de tópicos no Telegram para cada demanda, roteamento de mensagens por thread_id, mapeamento persistido thread_id ↔ demand_id
- `demand-context-tracking`: Rastreamento de contexto por demanda (quem criou, em qual chat, qual thread), propagação de thread_id pelo pipeline até as respostas dos agentes

### Modified Capabilities
- `messaging-bus`: Interface ganha suporte a thread_id opcional em send_message/send_photo/notify, novo método create_thread, handlers extraem message_thread_id e from_user.id
- `orchestrator`: Roteamento no daemon deixa de usar ID fixo "squad-lead-session", engine propaga demand context (thread_id) para callbacks de agentes

## Impact

- **src/messaging/interface.py** — novos parâmetros thread_id nos métodos, novo método abstrato create_thread
- **src/messaging/telegram.py** — handlers extraem thread_id e from_user.id, _send propaga message_thread_id, novo create_forum_topic
- **src/messaging/cli.py** — implementação no-op de create_thread para compatibilidade
- **src/daemon.py** — roteamento por thread_id, mapeamento thread↔demand, criação de tópicos ao iniciar demanda, separação chat_id/user_id
- **src/orchestrator/engine.py** — propaga thread_id nos callbacks de agentes (send_message, report_progress, send_image)
- **src/orchestrator/tools.py** — RunningAgent pode incluir thread_id para roteamento de respostas
- **src/orchestrator/prompt_builder.py** — status de agentes agrupado por demanda com demand_id visível
- **tests/** — testes para roteamento, mapeamento, fallback modo flat
