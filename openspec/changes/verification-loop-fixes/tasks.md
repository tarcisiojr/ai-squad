## 1. Verification loop

- [x] 1.1 Criar dataclass VerificationResult(passed: bool, details: str) em tools.py
- [x] 1.2 Implementar _verify_completion(agent_name, resultado, workspace) no engine — verifica marcador e tasks.md por tipo de agente
- [x] 1.3 Integrar verification no _on_agent_done — se falha, re-invoca agente com feedback (MAX_RETRIES=2)
- [x] 1.4 Quando verificacao falha apos MAX_RETRIES, marcar como "incomplete" e notificar usuario

## 2. Contexto completo no Squad Lead

- [x] 2.1 Passar resultado do agente + VerificationResult ao _trigger_squad_lead
- [x] 2.2 Incluir detalhes da verificacao no prompt do Squad Lead (ex: "Dev concluiu, verificacao: passed" ou "Dev concluiu, verificacao: failed — 3 tasks pendentes")

## 3. Mensagens nao-truncadas

- [x] 3.1 Aumentar preview de 200 para 2000 chars no _on_agent_done

## 4. Race condition

- [x] 4.1 Adicionar user_id ao RunningAgent dataclass
- [x] 4.2 Substituir self._current_user_id por running.user_id em _on_agent_done, _trigger_squad_lead e callbacks
- [x] 4.3 Substituir self._current_demand_id por running.demand_id nos mesmos locais

## 5. Testes

- [x] 5.1 Testes para verify_completion (Dev com tasks pendentes, Dev completo, PO com/sem marcador, QA)
- [x] 5.2 Testes para re-invocacao (verificacao falha → re-invoca → verifica de novo)
- [x] 5.3 Testes para MAX_RETRIES (apos 2 falhas, marca incomplete)
- [x] 5.4 Verificar cobertura >= 80%
