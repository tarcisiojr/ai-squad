---
name: kanban-force-cli
description: |
  CLI `kf` para interagir com a API do Kanban Force via bash.
  Usa menos contexto que o MCP — ideal para operações via shell.
  Output JSON por padrão (stdout limpo); logs vão para stderr.
license: MIT
metadata:
  author: kanban-force
  version: "2.0"
  updated: "2026-03-14"
  changelog: "Regras críticas; friendlyId correto; --parent em create; hierarquia de tipos; novos comandos: attachment, list, user search, card count/ancestors/ancestors, solicitation list, board members; paths jq corretos; tabela de erros comuns"
---

# Kanban Force CLI (`kf`) — Referência Compacta

---

## 🔴 REGRAS CRÍTICAS

### 1. Buscar card por código usa `friendlyId`, não `name`

```bash
# ✅ CORRETO
kf card list --where "friendlyId:OPS-505D"

# ❌ ERRADO — friendlyId não fica no campo name
kf card list --where "name:*OPS-505D*"
```

### 2. `status:Ativo` é obrigatório em toda busca de cards

Omitir retorna cards descartados, arquivados e concluídos misturados com os ativos.

```bash
# ✅ Sempre incluir
kf card list --where "boardId:<id>,status:Ativo"

# ❌ Retorna lixo
kf card list --where "boardId:<id>"
```

Exceção: quando o usuário pedir explicitamente outro status (`Arquivado`, `Descartado`, etc.)

### 3. Colunas ficam em `.lanes[].columns[]`, NÃO em `.columns[]`

```bash
# ✅ CORRETO
kf board get $BOARD_ID | jq -r '.lanes[].columns[] | select(.name=="Concluído") | ._id'

# ❌ ERRADO — retorna null
kf board get $BOARD_ID | jq -r '.columns[] | select(.name=="Concluído") | ._id'
```

### 4. `kf card update --column` é proibido pela API

Use `kf card move` (mesmo board) ou `kf card transfer` (outro board).

### 5. Parâmetros `<id>` sempre recebem ObjectId (24 hex), nunca friendlyId

```bash
# ✅
kf card move 698f5f171e1c571f53db46ca --column 61e94d58b56da80010865974

# ❌ Causa erro
kf card move TST-46CA --column ...
```

---

## Setup

```bash
uv tool install -e /path/to/mcp-kanban-force
kf --help
```

## Autenticação

```bash
kf auth login                        # Abre browser (Playwright), salva tokens
kf auth logout                       # Remove tokens salvos
kf auth token "Bearer eyJ..."        # Token manual (sem browser)
kf me                                # Dados do usuário autenticado
```

Tokens: `~/.mcp/kanban-force/tokens.json` (compartilhado com MCP)

## Formato de saída

```bash
kf board list                        # JSON (padrão, otimizado para LLM)
kf board list --format table         # Tabela rich (para humanos)
```

## Sintaxe Querify (`--where`)

```
campo:valor                          # filtro exato
campo:*termo*                        # wildcard (contém)
campo:val1|val2                      # OR no mesmo campo
campo1:v1,campo2:v2                  # AND (múltiplos campos)
$OR(campo1:*x*||campo2:*x*)          # OR entre campos diferentes
```

### Campos filtráveis — Cards

| Campo | Tipo | Exemplos |
|---|---|---|
| `friendlyId` | string exato | `friendlyId:OPS-505D` |
| `boardId` | ObjectId | `boardId:61e94b1db56da8001086587a` |
| `status` | enum | `status:Ativo` · `status:Arquivado` · `status:Descartado` |
| `blocked` | boolean | `blocked:true` · `blocked:false` |
| `deleted` | boolean | `deleted:false` |
| `name` | string/wildcard | `name:*deploy*` |
| `type` | ObjectId | `type:61802f4b675210c427d61db7` |
| `currentColumn` | ObjectId | `currentColumn:61e94d58b56da80010865974` |
| `owners` | ObjectId | `owners:61e86bc6b56da80010864401` |
| `tags` | string | `tags:backend` · `tags:backend\|frontend` |

**Exemplos combinados:**
```bash
# Cards ativos de um board
kf card list --where "boardId:<id>,status:Ativo"

# Cards bloqueados de um board
kf card list --where "boardId:<id>,blocked:true"

# Cards de um responsável em uma coluna específica
kf card list --where "owners:<userId>,currentColumn:<colId>"

# Cards de um tipo específico não deletados
kf card list --where "boardId:<id>,type:<typeId>,deleted:false"

# Busca por código amigável (exato)
kf card list --where "friendlyId:OPS-505D"

# Busca por trecho do nome
kf card list --where "name:*deploy*"

# Múltiplos status
kf card list --where "boardId:<id>,status:Ativo|Arquivado"
```

### Campos filtráveis — Boards

| Campo | Tipo | Exemplos |
|---|---|---|
| `active` | boolean | `active:true` · `active:false` |
| `isPublic` | boolean | `isPublic:true` |
| `name` | string/wildcard | `name:*ops*` |

**Exemplos:**
```bash
kf board list                                    # boards públicos ativos (padrão)
kf board search "ops"                            # busca por nome/descrição
```

## Boards

```bash
kf board list                        # Boards públicos ativos
kf board get <id>                    # Detalhes + colunas + cards
kf board search "meu projeto"        # Buscar por nome/descrição
kf board user <user-id>              # Boards de um usuário
kf board members <board-id>          # Membros do board
```

## Dashboards

```bash
kf dashboard user <user-id>          # Dashboards do usuário
kf dashboard user <id> --limit 10 --order createdAt:desc
```

## Cards — Leitura

```bash
kf card list --where "boardId:<id>"                  # Listar cards de um board
kf card list --where "boardId:<id>,status:Ativo"     # Só ativos
kf card list --where "friendlyId:OPS-505D"           # Buscar por código amigável (exato)
kf card list --where "name:*palavra*"                # Buscar por trecho do nome
kf card list --where "boardId:<id>" --limit 20 --order createdAt:desc
kf card count --where "boardId:<id>,status:Ativo"  # Contar cards com filtros
kf card get <id>                               # Detalhes hierárquicos
kf card ancestors <id>                         # Cards ancestrais (hierarquia ascendente)
kf card metrics <id>                           # Métricas
kf card movements <id>                         # Histórico de movimentações (com detalhes de owners)
kf card history <id>                           # Resumo de alterações
```

## Cards — Escrita

```bash
# Criar card raiz
kf card create --name "Task" --board <bId> --column <colId> --type <typeId>
kf card create --name "Task" --board <bId> --column <colId> --type <typeId> \
  --desc "Descrição" --owners <userId> --tags backend --dt-end 2025-12-31

# Criar card filho (--parent com ObjectId do pai)
# ⚠️  STK/OPS/IMP/BUG não aceitam filhos — use apenas tipos com descendentes
kf card create --name "Subtarefa X" --board <bId> --column <colId> \
  --type 62d82213f38c4880916f0231 --parent <parentCardId>

# Atualizar (GET automático + merge — só passe o que quer alterar)
kf card update <id> --name "Novo nome"
kf card update <id> --desc "Nova descrição"
kf card update <id> --perc-done 75 --size "M"
# ⚠️  NÃO use --column para mover — use kf card move ou kf card transfer

# Tarefas (tasks)
kf card update <id> --task "Nome da tarefa"                          # adicionar
kf card update <id> --task "A" --task "B"                           # múltiplas
kf card update <id> --remove-task <taskId>                          # remover
kf card update <id> --rename-task "<taskId>:Novo nome"              # renomear
kf card update <id> --task-due "<taskId>:2026-04-30"                # definir prazo (ISO)
kf card update <id> --task-owner "<taskId>:<userId>"                # definir responsável
# Nota: os 4 status visuais (Pendente/Em andamento/Bloqueado/Concluído) não são
# settable via REST API — são controlados somente pela interface web.

# Mover (mesmo board) — requer o ObjectId da coluna destino
kf card move <id> --column <colId>

# Transferir (outro board)
kf card transfer <id> --column <colId>

# Para obter o ObjectId de uma coluna: colunas ficam em .lanes[].columns[]
# Exemplo: DONE_COL=$(kf board get <boardId> | jq -r '.lanes[].columns[] | select(.name=="Concluído") | ._id')

# Bloquear / Desbloquear
# ⚠️  Requisitos do bloqueio:
#   - --reason: mínimo 10 caracteres
#   - --type: ObjectId do tipo de bloqueio (recomendado)
#
# Passo 1: obter os tipos de bloqueio disponíveis
kf list block-types 2>/dev/null | jq '.[] | {id: ._id, titulo: .title}'
# Tipos disponíveis:
#   657125b59a392aabbedded95  Aguardando definição/aprovação
#   657125b59a392aabbedded96  Aguardando Dependência Externa
#   657125b59a392aabbedded97  Aguardando Recursos de Tecnologia
#   6908bd1a016ca143e54c3396  Ambientes Instáveis e/ou Inoperante
#   657125b59a392aabbedded98  Ausência de Colaborador
#   657125b59a392aabbedded99  Limite de WIP excedido
#   657125b59a392aabbedded9a  Mudança de Prioridade/Planejamento
#   657125b59a392aabbedded9b  Mudança no Escopo da tarefa
#   657125b59a392aabbedded9c  Outro
#   6905028801536ca8275a01d4  VPN Instável / Inoperante
#
# Passo 2: bloquear o card
kf card block <id> --reason "Aguardando aprovação do time de produto" --type 657125b59a392aabbedded95
kf card block <id> --reason "Dependência de outro time" --type 657125b59a392aabbedded96
kf card block <id> --reason "Motivo detalhado aqui" --type 657125b59a392aabbedded9c  # Outro
kf card unblock <id>

# Arquivar / Descartar / Deletar
kf card archive <id1> <id2> <id3>              # múltiplos ids
kf card discard <id>
kf card delete <id>                            # permanente (admin)

# Like (toggle)
kf card like <id>
```

## Anexos

```bash
kf attachment list <card-id>                   # Listar anexos de um card
kf attachment upload <card-id> <arquivo>       # Enviar arquivo como anexo
kf attachment download <attachment-id>         # Baixar arquivo (salva com nome do ID)
kf attachment download <attachment-id> --out arquivo.pdf   # Salvar com nome específico
kf attachment delete <card-id> <att-id>        # Deletar um anexo
kf attachment delete <card-id> <id1> <id2>     # Deletar múltiplos
```

## Comentários

```bash
kf comment list <card-id>
kf comment add <card-id> --text "Comentário aqui"
kf comment update <card-id> <comment-id> --text "Novo texto"
kf comment delete <card-id> <comment-id>
```

## Riscos

```bash
kf risk list <card-id>
kf risk add <card-id> --name "Atraso" --probability 60 --impact 0.8
kf risk add <card-id> --name "Atraso" --probability 60 --impact 0.8 \
  --desc "Detalhe" --due-date 2026-04-01 --delegated-to <userId>
kf risk update <card-id> <risk-id> --name "Atraso" --probability 40 --impact 0.5
kf risk update <card-id> <risk-id> --name "X" --probability 10 --impact 0.2 \
  --due-date 2026-05-01 --delegated-to <userId>
kf risk delete <card-id> <risk-id>
```

## Usuários

```bash
kf user list                                   # Todos os usuários
kf user list --where "name:*João*"             # Filtro por nome
kf user search "tarcísio"                      # Busca por nome ou e-mail (autocompletar)
```

## Metadados e Listas

```bash
kf type list                                   # Tipos de card ativos
kf type list --where "active:true" --limit 20

kf list block-types                            # Tipos de bloqueio (para kf card block --type)
kf list block-types --format table             # Em formato de tabela
kf list get <Tipo>                             # Qualquer lista por tipo
```

### Hierarquia de tipos de card

```
STRG (Strategy)
 └── INI (Iniciativa)
      └── EPC (Épico)
           └── UST (User Story) | TST (História técnica)
                └── STK (Subtarefa)
```

> ⚠️ **STK, OPS, IMP, BUG** não aceitam cards filhos — nunca use `ancestralCard` apontando para esses tipos.

## Solicitações

```bash
kf solicitation list                           # Minhas solicitações (padrão)
kf solicitation list --all                     # Todas as solicitações
kf solicitation list --text "palavra" --from 2025-01-01 --to 2025-12-31
kf solicitation list --show-canceled           # Incluir canceladas
kf solicitation list --page 2 --limit 20
kf solicitation get <id>
kf solicitation events <id>
kf solicitation event-add <id> --origin "CI/CD" --event "GMUD Aberta"
kf solicitation event-add <id> --origin "Deploy" --event "Implantado" \
  --observation "Versão 2.3.1" --url "https://..."
```

## Fluxo típico para LLM

```bash
# 1. Descobrir boards disponíveis
kf board list | jq '.[].name'

# 2. Listar cards ATIVOS de um board (sempre status:Ativo)
BOARD_ID=$(kf board list | jq -r '.[] | select(.name=="Meu Board") | ._id')
kf card list --where "boardId:$BOARD_ID,status:Ativo" --limit 50

# 3. Buscar card por código amigável (friendlyId, não name)
kf card list --where "friendlyId:OPS-505D" | jq '.[0]'
CARD_ID=$(kf card list --where "friendlyId:OPS-505D" 2>/dev/null | jq -r '.[0]._id')

# 4. Buscar usuário por nome para obter o ID
USER_ID=$(kf user search "tarcísio" 2>/dev/null | jq -r '.[0]._id')

# 5. Contar cards ativos de um board
kf card count --where "boardId:$BOARD_ID,status:Ativo"

# 6. Atualizar apenas um campo (sem passar o resto)
kf card update $CARD_ID --name "Nome atualizado"

# 7. Mover card — colunas ficam em .lanes[].columns[], NÃO em .columns[]
DONE_COL=$(kf board get $BOARD_ID | jq -r '.lanes[].columns[] | select(.name=="Concluído") | ._id')
kf card move $CARD_ID --column $DONE_COL

# 8. Criar card filho
PARENT_ID=$(kf card list --where "friendlyId:TST-46CA" 2>/dev/null | jq -r '.[0]._id')
kf card create --name "Subtarefa X" --board $BOARD_ID --column $DONE_COL \
  --type 62d82213f38c4880916f0231 --parent $PARENT_ID

# 9. Upload de anexo e listar
kf attachment upload $CARD_ID /caminho/do/arquivo.pdf
kf attachment list $CARD_ID | jq '.[].originalName'
```

## ❌ Erros Comuns

| Erro | Causa | Solução |
|---|---|---|
| Cards descartados/arquivados na listagem | `status:Ativo` ausente | Sempre incluir `status:Ativo` no `--where` |
| Busca por código retorna vazio | Usar `name:*OPS-505D*` | Usar `friendlyId:OPS-505D` (exato) |
| `jq` retorna `null` para colunas | `.columns[]` direto | Usar `.lanes[].columns[]` |
| HTTP 500 em `kf card move` | `order` ausente | CLI já envia `order` automaticamente |
| API rejeita atualização da coluna | `--column` em `update` | Usar `kf card move` ou `kf card transfer` |
| `kf card delete` retorna 403 | Requer sysAdmin | Usar `kf card discard` |
| Bloqueio rejeitado | Motivo < 10 chars | `--reason` com mínimo 10 caracteres |
| Filho rejeitado pela API | Tipo pai é folha | STK/OPS/IMP/BUG não aceitam filhos |

## ObjectId vs friendlyId

- **ObjectId**: 24 hex chars — usado em todos os parâmetros `<id>`
- **friendlyId**: `OPS-505D` — use `--where "friendlyId:OPS-505D"` para buscar por código exato

## Exit codes

- `0` — sucesso
- `1` — erro (mensagem no stderr)
