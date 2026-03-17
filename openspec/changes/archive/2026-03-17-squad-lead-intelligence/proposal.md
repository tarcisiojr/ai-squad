# Proposal: Squad Lead Intelligence

## Problema

O Squad Lead atual opera como um "dispatcher burro" — recebe mensagem, delega, esquece. Isso causa 5 problemas críticos observados em produção:

1. **Confunde pergunta com demanda**: Toda mensagem do usuário vira `start_agent()`. Perguntas simples disparam o pipeline completo.
2. **Age fora de ordem**: Não consulta o estado atual antes de agir. Pode tentar iniciar Dev quando PO nem terminou.
3. **Não retoma processos parados**: Cada invocação começa do zero. Demandas que ficaram em `awaiting_plan_approval` são esquecidas.
4. **Não valida critérios de aceite**: `check_artifacts()` só verifica existência de arquivos, não qualidade ou completude.
5. **Fire-and-forget**: Delega e esquece. Não monitora progresso, não detecta agentes travados, não ajusta rota.

## Solução

Transformar o Squad Lead de um dispatcher reativo em um **coordenador com consciência situacional**, implementando 5 capacidades:

### 1. Intent Classifier (Prompt Engineering)
Classificar a mensagem do usuário ANTES de agir: pergunta? demanda? status? retomada?

### 2. State Awareness (Nova tool + prompt)
Tool `get_demand_state()` que retorna estado completo de demandas ativas. Squad Lead consulta ANTES de decidir.

### 3. Criteria Gate (Validação enriquecida)
`check_artifacts()` evolui para validar: specs têm critérios de aceite? tasks.md tem itens? QA report tem cobertura?

### 4. Squad Lead Journal (Memória entre sessões)
Arquivo `state/{demand_id}/squad-lead-journal.json` que persiste: decisões tomadas, próximo passo esperado, contexto acumulado.

### 5. Heartbeat Loop (Proatividade)
Daemon verifica periodicamente demandas paradas e aciona o Squad Lead para retomar.

## Escopo

### Incluído
- Reescrita do AGENTS.md do Squad Lead com classificação de intent
- Nova tool `get_demand_state()` no engine
- Enriquecimento de `check_artifacts()` com validação de qualidade
- Sistema de journal (persistência de decisões do Squad Lead)
- Heartbeat loop no daemon para retomada de processos parados
- Testes para todos os novos comportamentos

### 6. Remover adapter legado
Deletar `ClaudeCodeCLIAdapter` (`claude --print`, single-shot) e usar exclusivamente o `ClaudeAgentSDKAdapter` que já suporta agent loop completo com tool use.

### 7. Artifact-Based Completion
Substituir markers textuais (`---SPEC_READY---`, `---DONE---`, `---QA_DONE---`) por verificação de artefatos reais via Criteria Gate.

### Excluído
- Mudança no fluxo de estados (máquina de estados permanece igual)
- Mudança nos agentes PO/Dev/QA (além de remover markers)
- Vector search / embeddings (complexidade desnecessária para v1)
- Interface web / dashboard

## Motivação

Inspirado em padrões do OpenClaw (heartbeats, memory, session management, tool-loop detection) adaptados para nosso contexto de dev team autônomo. O objetivo é que o Squad Lead funcione como um **tech lead humano**: sabe o que está acontecendo, sabe o que falta fazer, retoma o que ficou parado, e não confunde uma pergunta com um pedido.

## Impacto

- **Arquivos modificados**: ~6 arquivos existentes
- **Arquivos novos**: ~2 (journal, heartbeat)
- **Testes**: ~15-20 novos testes
- **Risco**: Baixo — mudanças aditivas, sem breaking changes na máquina de estados
