# orchestrator

## Purpose

Motor de orquestração que controla o ciclo de vida de demandas através de máquina de estados, despacho de agentes e roteamento de decisões humanas — totalmente desacoplado de providers concretos.

## Requirements

### Requirement: Máquina de estados do ciclo de vida
O orquestrador SHALL gerenciar o ciclo de vida de cada demanda através dos estados: `idle` → `po_working` → `awaiting_plan_approval` → `dev_working` → `awaiting_pr_approval` → `ci_running` → `qa_validating` → `done`. Transições inválidas SHALL ser rejeitadas com erro.

#### Scenario: Ciclo completo bem-sucedido
- **WHEN** uma nova demanda é recebida e todos os passos são aprovados
- **THEN** a demanda transiciona por todos os estados em ordem até `done`

#### Scenario: Transição inválida rejeitada
- **WHEN** uma tentativa de transição de `idle` para `dev_working` é feita
- **THEN** o sistema rejeita a transição e mantém o estado atual

### Requirement: Persistência de estado
O orquestrador SHALL persistir o estado de cada demanda em arquivo JSON. O estado SHALL sobreviver a reinicializações do sistema.

#### Scenario: Recuperação após reinício
- **WHEN** o sistema reinicia com uma demanda em estado `dev_working`
- **THEN** o orquestrador carrega o estado do JSON e retoma a partir de `dev_working`

### Requirement: Despacho de agentes via adapter
O orquestrador SHALL disparar agentes exclusivamente via `AIAgentAdapter` interface. O orquestrador SHALL NOT importar ou conhecer implementações concretas de IA.

#### Scenario: Despacho de agente PO
- **WHEN** uma demanda entra no estado `po_working`
- **THEN** o orquestrador invoca o adapter com o prompt e contexto do agente PO registrado no registry

### Requirement: Roteamento de decisões humanas
O orquestrador SHALL interceptar chamadas `ask()` dos agentes e rotear para o barramento via interface `MessageBus`. O orquestrador SHALL NOT interagir diretamente com canais de mensageria.

#### Scenario: Agente solicita aprovação de plano
- **WHEN** o agente PO emite um pedido de aprovação via `ask()`
- **THEN** o orquestrador envia a pergunta ao usuário via `MessageBus.send_approval_request` e retorna a resposta ao agente

### Requirement: Gerenciamento de worktrees git
O orquestrador SHALL criar e gerenciar worktrees git separadas para cada subagente, garantindo isolamento de código entre agentes trabalhando em paralelo.

#### Scenario: Dois agentes dev trabalhando em paralelo
- **WHEN** dois subagentes dev são disparados simultaneamente
- **THEN** cada um recebe uma worktree git independente e não interfere no trabalho do outro

### Requirement: Desacoplamento de providers
O orquestrador SHALL NOT ter conhecimento de qual provider de IA ou mensageria está em uso. Toda comunicação SHALL ser feita exclusivamente via interfaces ABC.

#### Scenario: Troca de provider não afeta orquestrador
- **WHEN** o provider de IA é trocado de Claude Code para Gemini no platform.yaml
- **THEN** o orquestrador continua funcionando sem nenhuma alteração em seu código
