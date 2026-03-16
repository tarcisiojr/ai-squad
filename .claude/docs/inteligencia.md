# Arquitetura de Inteligencia do ai-dev-team

## Visao Geral

O sistema usa 6 camadas de inteligencia que trabalham juntas para que os agentes
aprendam, lembrem e se recuperem de falhas entre demandas e restarts.

## 1. LessonsStore — Aprendizado entre demandas

**Arquivo**: `src/orchestrator/lessons.py`

Persiste licoes aprendidas em `state/lessons.json`. Cada licao registra:
- Categoria (bug, retrabalho, timeout, padrao, processo)
- Problema (o que deu errado)
- Solucao (como resolver/evitar)
- Agente e demanda de origem

**Como funciona**:
- Registrado automaticamente quando agentes falham ou verificacao reprova
- Squad Lead pode registrar manualmente via tool `learn_lesson`
- Licoes relevantes sao injetadas no prompt de TODOS os agentes (nao so Squad Lead)
- Busca por keywords do prompt atual nas licoes
- Limite: 50 licoes, prioriza mais usadas e recentes
- Injecao: maximo 10 licoes por prompt

**Fluxo**:
```
Agente falha → engine registra licao → proxima execucao carrega licoes relevantes
                                        ↓
                                    Agente recebe no prompt:
                                    "## Licoes aprendidas (evite repetir erros)"
```

## 2. ConversationStore — Historico de conversa

**Arquivo**: `src/orchestrator/conversation.py`

Persiste historico de mensagens usuario ↔ agentes por demanda.
Sobrevive a restarts do Docker.

- Salva mensagens do usuario e respostas do Squad Lead
- Salva resultados dos agentes quando concluem
- Limite de 20 mensagens no contexto (resume mensagens antigas)
- Injetado no prompt do Squad Lead como "## Historico da conversa"

## 3. JournalStore — Decisoes e estado

**Arquivo**: `src/orchestrator/journal.py`

Registra decisoes tomadas pelo Squad Lead com:
- Acao (delegated_to_po, dev_completed, etc.)
- Fase atual da demanda
- Proxima acao esperada (agente + descricao)
- Notas de contexto

Usado para retomada automatica de demandas paradas.

## 4. Monitor do Squad Lead

**Arquivo**: `src/orchestrator/engine.py` (atributos `_squad_lead_empty_count`)

Detecta quando o Squad Lead trava (respostas vazias consecutivas):
- Conta respostas vazias sequenciais
- Apos 3 vazias: reseta sessao automaticamente
- Notifica usuario: "Squad Lead parece travado. Sessao resetada."
- Resposta valida zera o contador

## 5. ProductContextCollector — Contexto multinivel

**Arquivo**: `src/orchestrator/context.py`

Coleta contexto do repositorio para enriquecer prompts:

**3 niveis de contexto**:
1. CLAUDE.md da raiz do workspace (regras do projeto guarda-chuva)
2. AGENTS.md do submodulo (regras especificas do modulo, se configurado)
3. README.md + arvore de diretorios + specs existentes

**Cache com TTL de 60s** — evita reler disco a cada chamada de agente.

**Submodulos**: Configurados no `config.yaml` por agente:
```yaml
agents:
  dev-backend:
    submodules:
      - path: "packages/api"
        description: "API REST"
```

## 6. Verificacao Dinamica de Agentes

**Arquivo**: `src/orchestrator/engine.py` (`_classify_agent_role`)

Classifica o papel de qualquer agente pelo conteudo do AGENTS.md (nao por nome):
- Palavras "openspec" + "proposal"/"specs" → role: spec
- Palavras "tasks.md" + "implemente"/"codigo" → role: dev
- Palavras "aprovado"/"rejeitado" + "review"/"validar" → role: review
- Nenhuma match → role: generic (sem verificacao especifica)

Verificacoes por role:
- **spec**: Valida artefatos openspec com conteudo minimo (50 bytes)
- **dev**: Valida se tasks.md tem todos os `[ ]` marcados como `[x]`
- **review**: Valida se resultado contem veredicto (APROVADO/REJEITADO)

## 7. Timeout por Agente

Configuravel por agente no `config.yaml` via campo `timeout`:
- Prioridade: config do agente > dev_timeout > agent_timeout padrao
- Passado via contexto ate o adapter SDK

## 8. Heartbeat Loop

**Arquivo**: `src/daemon.py`

Verifica periodicamente (default 5min):
- Demandas paradas ha mais de 30min sem update → retoma via Squad Lead
- Aprovacoes pendentes ha mais de 1h → envia lembrete ao usuario
- Max 3 retentativas automaticas por demanda

## Fluxo Completo de uma Demanda

```
Usuario envia mensagem
    ↓
Daemon recebe via Telegram
    ↓
Squad Lead classifica intent (PERGUNTA/DEMANDA/RETOMADA/etc.)
    ↓ (se DEMANDA)
start_agent("po", "Especificar: ...")
    ↓
PO cria artefatos via openspec (proposal → specs → design → tasks)
    ↓ ---SPEC_READY---
Engine verifica artefatos (conteudo minimo) → Squad Lead decide
    ↓
start_agent("dev-backend", "Implementar tasks backend de: ...")
start_agent("dev-frontend", "Implementar tasks frontend de: ...")
    ↓ (paralelo)
Ambos concluem → ---DONE---
Engine verifica tasks.md (todos [x]?)
    ↓
start_agent("code-review", "Revisar codigo de: ...")
    ↓
Se APROVADO → start_agent("qa", "Validar: ...")
Se REJEITADO → volta ao Dev com feedback + registra licao
    ↓
QA valida → ---QA_DONE---
    ↓
Squad Lead: "Tudo pronto! QA aprovou."
```
