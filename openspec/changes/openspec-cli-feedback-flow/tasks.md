## 1. AGENTS.md com instrucoes de openspec CLI

- [x] 1.1 Reescrever agents/squad-lead/AGENTS.md — instruir a usar openspec status para validar artefatos, forcar fluxo completo (proposal → specs → design → tasks → dev), dar feedback ao usuario em cada fase
- [x] 1.2 Reescrever agents/po/AGENTS.md — instruir a usar openspec new change, openspec instructions para cada artefato, gerar proposal → specs → design → tasks na ordem correta
- [x] 1.3 Reescrever agents/dev/AGENTS.md — instruir a ler tasks.md e implementar task por task, marcando [ ] → [x] conforme conclui
- [x] 1.4 Ajustar agents/qa/AGENTS.md — instruir a validar contra specs/ gerados pelo openspec

## 2. Feedback periodico no engine

- [x] 2.1 Criar task em background no dispatch_agent que envia feedback ao Telegram a cada 30s com formato "[<agente>] Trabalhando... (<tempo>)"
- [x] 2.2 Cancelar task de feedback quando agente conclui
- [x] 2.3 Combinar com _keep_typing existente (typing + feedback na mesma task)

## 3. Verificar openspec no Docker

- [x] 3.1 Verificar que o CLI openspec esta instalado e no PATH dentro do container Docker
- [x] 3.2 Se nao, adicionar instalacao no Dockerfile ou pyproject.toml

## 4. Testes

- [x] 4.1 Testes para feedback periodico (task em background, cancelamento)
- [x] 4.2 Verificar cobertura >= 80%
