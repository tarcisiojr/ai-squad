## 1. Formatação Telegram (texto plano)

- [x] 1.1 Remover todo `parse_mode="Markdown"` do `telegram.py` — enviar tudo como texto plano
- [x] 1.2 Remover `_send_safe` com fallback Markdown — enviar direto sem parse_mode
- [x] 1.3 Limpar prefixos de mensagem (remover `*bold*` syntax, usar texto simples)

## 2. Configuração dinâmica de personas

- [x] 2.1 Adicionar campo `command` nas personas do config.yaml template (ex: `command: "/po"`)
- [x] 2.2 Carregar personas no PlatformConfig com campo `command` (fallback: `/<nome>`)
- [x] 2.3 Refatorar daemon.py — gerar `AGENT_COMMANDS` dinamicamente da config em vez de hardcoded
- [x] 2.4 Gerar `/help` dinamicamente listando comandos das personas
- [x] 2.5 Refatorar engine.py — eliminar `AGENT_LABELS` hardcoded, receber personas da config
- [x] 2.6 Passar personas para o engine no construtor do daemon

## 3. Conversa fluida (modo CHAT vs APPROVAL)

- [x] 3.1 Refatorar `_agent_conversation` — modo CHAT por padrão (sem botões, texto livre ida-e-volta)
- [x] 3.2 Detectar marcadores (`---SPEC_READY---`, `---DONE---`, `---QA_DONE---`) na resposta do agente
- [x] 3.3 Quando marcador detectado: remover do texto, entrar em modo APPROVAL (mostrar botões)
- [x] 3.4 No modo APPROVAL, se rejeitado: pedir feedback e reenviar ao agente (volta ao modo CHAT)
- [x] 3.5 Fallback: após 10 turnos sem marcador, perguntar ao usuário se quer finalizar
- [x] 3.6 Atualizar AGENTS.md do PO com instruções de marcador `---SPEC_READY---`
- [x] 3.7 Atualizar AGENTS.md do Dev com instruções de marcador `---DONE---`
- [x] 3.8 Atualizar AGENTS.md do QA com instruções de marcador `---QA_DONE---`

## 4. Fluxo OpenSpec no ciclo de demanda

- [x] 4.1 Refatorar `run_demand_cycle` — PO conversa em modo CHAT, salva proposal.md quando aprovado
- [x] 4.2 Dev recebe proposal.md no contexto, implementa de fato no workspace
- [x] 4.3 Dev salva design.md em `specs/<demand-id>/` quando marca ---DONE---
- [x] 4.4 QA recebe proposal.md + design.md no contexto, valida contra specs
- [x] 4.5 Após Dev marcar ---DONE---, verificar se houve mudanças no workspace (git status)

## 5. Web search para PO

- [x] 5.1 Adicionar parâmetro `allowed_tools` no ClaudeAgentSDKAdapter
- [x] 5.2 Quando agente é PO, habilitar `WebSearchTool` nas options do SDK
- [x] 5.3 Instrução no AGENTS.md do PO para usar busca web quando necessário

## 6. Feedback de progresso e timeout

- [x] 6.1 Aumentar timeout do Dev para 600s (10 min) no config.yaml template
- [x] 6.2 Implementar notificação periódica "Dev trabalhando..." a cada 30s durante execução longa
- [x] 6.3 Após timeout ou ---DONE--- sem mudanças, notificar usuário

## 7. Testes

- [x] 7.1 Testes para modo CHAT (sem botões, texto livre)
- [x] 7.2 Testes para modo APPROVAL (marcador detectado, botões mostrados)
- [x] 7.3 Testes para comandos dinâmicos da config
- [x] 7.4 Testes para texto plano no Telegram (sem parse_mode)
- [x] 7.5 Testes para fallback de turnos
- [x] 7.6 Verificar cobertura >= 80%
