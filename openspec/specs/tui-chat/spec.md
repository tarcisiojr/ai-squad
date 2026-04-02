# Spec: TUI Chat

## Requisitos

### Chat Panel
- Exibe mensagens com scroll automático (acompanha novas mensagens)
- Cada mensagem mostra avatar + nome da persona (ex: `👨‍💼 Squad Lead`)
- Mensagens do usuário mostram `👤 Você`
- Suporte a texto longo com word wrap
- Notificações exibidas com destaque (`🔔`)
- Progresso de agentes mostrado inline (ex: `⚙️ Dev Backend: Analisando...`)

### Input Widget
- Prompt `> ` sempre visível na parte inferior
- Enter envia mensagem
- Input não bloqueia a renderização do chat (async)
- Suporte a histórico de comandos (setas cima/baixo) — via Textual built-in

### Comandos
- `/help` — mostra ajuda
- `/status` — status dos agentes
- `/stop` — para agentes
- `/skills` — lista skills
- `/quit` ou Ctrl+C — encerra o daemon

### Aprovações
- `ask_user()` — exibe pergunta no chat, foco vai para input
- `send_approval_request()` — exibe opções numeradas no chat, aguarda número

## Cenários

### Cenário 1: Fluxo básico
1. Usuário inicia `ai-squad start MeuTime --tui`
2. TUI abre com chat vazio e header com nome do time
3. Usuário digita `Migrar módulo X para v5`
4. Mensagem aparece no chat como `👤 Você`
5. Squad Lead processa e resposta aparece como `👨‍💼 Squad Lead`
6. Se delegar, progresso do agente aparece inline

### Cenário 2: Aprovação
1. Pipeline atinge checkpoint
2. Chat mostra pergunta com opções numeradas
3. Usuário digita número
4. Pipeline avança

### Cenário 3: Múltiplos agentes
1. Squad Lead delega a PO e Dev em paralelo
2. Mensagens de progresso de ambos aparecem intercaladas no chat
3. Quando cada um termina, resultado aparece com persona correspondente
