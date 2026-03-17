# Design: Squad Lead Intelligence

## Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DAEMON (daemon.py)                          │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐    │
│  │ Telegram     │  │ Healthcheck  │  │ Heartbeat Loop (NOVO)  │    │
│  │ Polling      │  │ Loop         │  │                        │    │
│  │              │  │              │  │ - check stalled demands│    │
│  │              │  │              │  │ - send reminders       │    │
│  │              │  │              │  │ - auto-resume          │    │
│  └──────┬───────┘  └──────────────┘  └───────────┬────────────┘    │
│         │                                         │                 │
│         └─────────────────┬───────────────────────┘                 │
│                           ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                  OrchestrationEngine                         │    │
│  │                                                              │    │
│  │  run_squad_lead()                                            │    │
│  │    │                                                         │    │
│  │    ├─ 1. Lê journal (NOVO) → contexto de sessões anteriores │    │
│  │    ├─ 2. Lê state → consciência de estado                   │    │
│  │    ├─ 3. Injeta tudo no prompt do Squad Lead                │    │
│  │    └─ 4. Squad Lead decide com contexto completo            │    │
│  │                                                              │    │
│  │  Tools MCP expostas ao Squad Lead:                           │    │
│  │    ├─ start_agent()          (existente)                     │    │
│  │    ├─ get_running_agents()   (existente)                     │    │
│  │    ├─ report_progress()      (existente)                     │    │
│  │    ├─ check_artifacts()      (ENRIQUECIDO)                   │    │
│  │    ├─ get_demand_state()     (NOVO)                          │    │
│  │    └─ read_journal()         (NOVO)                          │    │
│  │                                                              │    │
│  │  Persistência:                                               │    │
│  │    ├─ StateManager           (existente)                     │    │
│  │    ├─ ConversationStore      (existente)                     │    │
│  │    └─ JournalStore (NOVO)                                    │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## Decisões de Design

### D0: Remover ClaudeCodeCLIAdapter (single-shot legado)

**Decisão**: Deletar `src/adapters/claude_code.py` e usar exclusivamente o `ClaudeAgentSDKAdapter`.

**Motivo**: O adapter CLI (`claude --print`) é single-shot: manda prompt, recebe resposta, sem tool use, sem iteração. O SDK adapter já suporta agent loop completo com 30+ turns, MCP tools, sessões persistentes, skills, e acesso a Read/Edit/Bash/Grep/Glob. Manter o adapter legado é código morto.

**Implicação**: Os agentes (PO, Dev, QA) já têm capacidade de execução equivalente a um humano usando Claude Code. O problema real é apenas a coordenação (Squad Lead), que é exatamente o que esta proposta resolve.

### D1: Intent Classification via Prompt (não código)

**Decisão**: Classificação de intent no AGENTS.md, não em código Python.

**Motivo**: O LLM é naturalmente bom em classificar intenção se instruído corretamente. Adicionar código Python para classificação seria over-engineering — um regex não vai capturar nuances como "continua aquilo do login" vs "cria um login". O AGENTS.md com exemplos claros resolve.

**Trade-off**: Menos determinístico que código, mas mais flexível e adaptável.

### D2: Journal como JSON (não banco de dados)

**Decisão**: Journal persiste como JSON no filesystem, seguindo o padrão do StateManager.

**Motivo**: Consistência com a arquitetura existente. StateManager e ConversationStore já usam JSON com escrita atômica. Adicionar SQLite ou outro banco seria complexidade desnecessária para v1.

**Caminho**: `state/{demand_id}/squad-lead-journal.json`

### D3: Heartbeat no Daemon (não cron externo)

**Decisão**: Heartbeat como asyncio task no daemon, não como cron job externo.

**Motivo**: O daemon já tem o event loop, as referências ao engine, e o message bus. Adicionar um cron externo introduziria sincronização, autenticação e estado compartilhado sem necessidade.

### D4: check_artifacts() enriquecido (não nova tool)

**Decisão**: Enriquecer a tool existente `check_artifacts()` com validações de qualidade, em vez de criar nova tool.

**Motivo**: O Squad Lead já sabe quando chamar `check_artifacts()`. Mudar o retorno para incluir validações detalhadas é mais simples que ensinar o Squad Lead a usar uma tool nova.

### D5: Artifact-Based Completion (não markers textuais)

**Decisão**: Remover o sistema de markers (`---SPEC_READY---`, `---DONE---`, `---QA_DONE---`) e usar o Criteria Gate para detectar conclusão.

**Motivo**: Markers são frágeis — dependem do LLM lembrar de escrever uma string mágica. Com o Criteria Gate já validando artefatos, os markers são redundantes. Artefatos reais são a prova de conclusão, não uma string no output.

**Benefício extra**: O retry passa a ter feedback específico ("faltam critérios de aceite em specs/auth") em vez de genérico ("coloque o marker ---SPEC_READY---").

### D6: Estado injetado no contexto (não tool obrigatória)

**Decisão**: Estado das demandas é injetado automaticamente no prompt do Squad Lead pelo engine, além de estar disponível como tool.

**Motivo**: Se depender do Squad Lead chamar `get_demand_state()`, ele pode esquecer (como esquece hoje). Injetar automaticamente garante que ele SEMPRE sabe o estado.

## Componentes Detalhados

### 1. JournalStore (novo arquivo: `src/orchestrator/journal.py`)

```python
class JournalStore:
    """Persiste decisões e contexto do Squad Lead por demanda."""

    def __init__(self, state_dir: str = "state"):
        self._state_dir = state_dir

    def create(self, demand_id: str, demand_text: str) -> dict:
        """Cria journal para nova demanda."""

    def add_decision(self, demand_id: str, action: str, detail: str):
        """Registra decisão tomada pelo Squad Lead."""

    def set_next_expected(self, demand_id: str, action: str, agent: str, description: str):
        """Define próxima ação esperada."""

    def add_context_note(self, demand_id: str, note: str):
        """Adiciona nota de contexto (info do usuário relevante)."""

    def read(self, demand_id: str) -> dict | None:
        """Lê journal de uma demanda."""

    def get_active_summaries(self) -> str:
        """Retorna resumo formatado de todos journals ativos."""

    def get_stalled(self, stall_timeout: int = 1800) -> list[dict]:
        """Retorna demandas paradas (sem atualização > timeout)."""
```

Escrita atômica seguindo padrão do StateManager (temp file + rename).

### 2. Heartbeat Loop (novo método em `src/daemon.py`)

```python
async def _heartbeat_loop(self):
    """Loop periódico que verifica demandas paradas e envia lembretes."""
    while not self._shutdown:
        await asyncio.sleep(self._config.heartbeat_interval)
        try:
            stalled = self._engine.get_stalled_demands()
            for demand in stalled:
                if demand.awaiting_approval:
                    await self._send_reminder(demand)
                elif demand.auto_retries < MAX_AUTO_RETRIES:
                    await self._resume_demand(demand)
                else:
                    await self._notify_stuck(demand)
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
```

### 3. AGENTS.md Reescrito (Squad Lead)

Estrutura principal:
```markdown
# Squad Lead

## PRIMEIRA COISA: Classifique a Mensagem
(intent classification com exemplos)

## SEGUNDA COISA: Consulte o Estado
(leia o contexto injetado de demandas ativas)

## TERCEIRA COISA: Decida a Ação
(tabela intent × estado → ação)

## Fluxo para Demandas Novas
(fluxo existente, mantido)

## Fluxo para Retomadas
(NOVO: como retomar processos parados)

## Validação de Artefatos
(NOVO: o que fazer quando check_artifacts falha)
```

### 4. Engine: Contexto Enriquecido para Squad Lead

No `run_squad_lead()`, antes de chamar o adapter:

```python
# Injeta estado atual no prompt
journal_summary = self._journal.get_active_summaries()
state_summary = self._get_all_demands_summary()
running_summary = self._get_running_agents_status()

context_injection = f"""
## Estado Atual do Sistema
{state_summary}

## Agentes em Execução
{running_summary}

## Histórico de Decisões (Journal)
{journal_summary}
"""
```

### 5. check_artifacts() Enriquecido

```python
async def _handle_check_artifacts(self, change_name: str) -> dict:
    phase = self._determine_phase(demand_id)
    checks = []

    if phase == "po_to_dev":
        checks.append(self._check_file_exists(f"proposal.md"))
        checks.append(self._check_specs_have_criteria(change_name))
        checks.append(self._check_tasks_minimum(change_name, min_items=3))
        checks.append(self._check_design_exists(change_name))
    elif phase == "dev_to_qa":
        checks.append(self._check_tasks_complete(change_name))
        checks.append(self._check_git_clean())
        checks.append(self._check_tests_pass())

    passed = all(c["passed"] for c in checks)
    return {
        "passed": passed,
        "phase": phase,
        "checks": checks,
        "summary": self._build_check_summary(checks),
        "action": self._suggest_action(checks) if not passed else None
    }
```

## Fluxo End-to-End (Revisado)

```
Usuário: "Cria endpoint de login"
    │
    ▼
Squad Lead invocado com:
  - AGENTS.md (com intent classifier)
  - Estado atual (nenhuma demanda ativa)
  - Journal (vazio)
    │
    ├─ Classifica: DEMANDA
    ├─ Consulta estado: nenhuma demanda ativa
    ├─ Decide: criar nova demanda
    ├─ start_agent("po", "Especificar: endpoint de login")
    ├─ Journal: registra decisão
    └─ Responde: "Delegado ao PO"
         │
         ▼ (PO conclui)
Squad Lead re-invocado com:
  - Estado: po_working → awaiting_plan_approval
  - Journal: {last_decision: delegated_to_po}
    │
    ├─ check_artifacts("endpoint-login")
    │   └─ Valida: proposal ✓, specs com critérios ✓, tasks 5 itens ✓
    ├─ Avança estado: awaiting_plan_approval
    ├─ Envia plano para aprovação do usuário
    └─ Journal: registra "artifacts_validated"
         │
         ▼ (Usuário 2h depois: "Aprovado")
Squad Lead invocado com:
  - Estado: awaiting_plan_approval
  - Journal: {next_expected: user_approval}
    │
    ├─ Classifica: APROVAÇÃO
    ├─ Consulta estado: demanda em awaiting_plan_approval
    ├─ Avança estado: dev_working
    ├─ start_agent("dev", "Implementar tasks")
    └─ Journal: registra "plan_approved, delegated_to_dev"
         │
         ▼ (Daemon reinicia, Dev não concluiu)
Heartbeat detecta:
  - Demanda "endpoint-login" em dev_working
  - Sem agente rodando
  - Journal: next_expected = dev_completion
    │
    ├─ Aciona Squad Lead: "RETOMADA: Dev não concluiu endpoint-login"
    └─ Squad Lead retoma: start_agent("dev", "Continuar: endpoint-login")
```

## Impacto nos Arquivos

| Arquivo | Tipo | Mudança |
|---------|------|---------|
| `src/adapters/claude_code.py` | **Deletado** | Adapter legado removido |
| `build/lib/src/adapters/claude_code.py` | **Deletado** | Build do adapter legado |
| `src/factory.py` | Existente | Remover registro do provider `claude-code` |
| `agents/squad-lead/AGENTS.md` | Existente | Reescrita completa com intent classifier |
| `agents/po/AGENTS.md` | Existente | Remover instrução de marker |
| `agents/dev/AGENTS.md` | Existente | Remover instrução de marker |
| `agents/qa/AGENTS.md` | Existente | Remover instrução de marker |
| `src/orchestrator/journal.py` | **Novo** | JournalStore |
| `src/orchestrator/engine.py` | Existente | Novas tools, contexto enriquecido, journal, artifact-based completion |
| `src/orchestrator/tools.py` | Existente | Novos dataclasses (JournalEntry, CheckResult) |
| `src/daemon.py` | Existente | Heartbeat loop |
| `platform.yaml` | Existente | Seção heartbeat, ai_provider atualizado |
| `tests/test_journal.py` | **Novo** | Testes do JournalStore |
| `tests/test_heartbeat.py` | **Novo** | Testes do heartbeat loop |
| `tests/test_engine_intelligence.py` | **Novo** | Testes de artifact-based completion |
