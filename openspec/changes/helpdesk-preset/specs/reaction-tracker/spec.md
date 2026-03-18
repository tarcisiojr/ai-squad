# Spec: Reaction Tracker

## Descrição
Captura reações do Telegram (👍/👎) em mensagens do bot e atualiza o score do documento fonte na knowledge base.

## Requisitos Funcionais

### Captura de reações
- DEVE registrar handler para `message_reaction` na Bot API do Telegram
- DEVE capturar reações em mensagens enviadas pelo bot (não em mensagens de usuários)
- DEVE suportar pelo menos: 👍 (positivo) e 👎 (negativo)
- PODE suportar reações customizadas no futuro

### Mapeamento mensagem → documento
- DEVE manter mapeamento `message_id → doc_path` em memória (dict)
- DEVE registrar o mapeamento quando o Atendente usa um documento para responder
- Mapeamento DEVE expirar após 24h (evita crescimento infinito)
- DEVE ser resiliente a msg_ids sem mapeamento (ignora silenciosamente)

### Atualização de score
- Ao receber 👍: incrementa `score` no frontmatter do .md (+1)
- Ao receber 👎: decrementa `score` no frontmatter do .md (-1, mínimo 0)
- DEVE ler, modificar e salvar o frontmatter atomicamente
- DEVE reindexar o documento no knowledge store após atualização
- DEVE logar a atualização: "Documento X: score 5 → 6 (👍)"

### Integração com TelegramMessageBus
- DEVE adicionar handler `MessageReactionHandler` no `_ensure_app()`
- DEVE expor callback `on_reaction(callback)` na interface MessageBus
- O callback recebe: `(chat_id, message_id, reaction_emoji, user_id)`

## Requisitos Não-Funcionais
- Mapeamento em memória: máximo 10.000 entries (LRU)
- Atualização de score: menos de 100ms
- DEVE funcionar mesmo sem knowledge store configurado (no-op)

## Cenários

### Reação positiva
```
1. Atendente responde msg_id=12345 usando doc "vpn-nao-conecta.md"
2. Sistema registra: { 12345: "atendimentos/vpn-nao-conecta.md" }
3. Usuário reage 👍 na msg_id=12345
4. Telegram envia update message_reaction
5. Handler busca: msg_id=12345 → "vpn-nao-conecta.md"
6. Lê frontmatter: score: 5
7. Atualiza: score: 6
8. Salva .md e reindexa
```

### Reação sem mapeamento
```
1. Usuário reage 👍 numa msg qualquer (sem doc associado)
2. Handler busca msg_id → não encontra
3. Ignora silenciosamente (log debug)
```

### Múltiplas reações no mesmo documento
```
1. Doc "reset-senha.md" com score: 3
2. Recebe 👍 → score: 4
3. Recebe 👍 → score: 5
4. Recebe 👎 → score: 4
→ Score reflete validação coletiva
```
