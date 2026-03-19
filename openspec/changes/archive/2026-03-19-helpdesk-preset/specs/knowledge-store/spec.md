# Spec: Knowledge Store

## Descrição
Módulo de busca na knowledge base com interface plugável (FTS5 ou qmd) e sistema de score por reforço.

## Requisitos Funcionais

### Busca
- DEVE buscar documentos .md em `knowledge/` por relevância textual
- DEVE retornar trechos relevantes, não o documento inteiro
- DEVE suportar backend FTS5 (padrão) e qmd (opcional)
- DEVE aplicar boost de score baseado em reações (👍 incrementa, 👎 decrementa)
- DEVE retornar metadados: path, título, score, vezes usado, última vez usado

### Indexação
- DEVE indexar todos os .md de `knowledge/atendimentos/` e `knowledge/documentacao/`
- DEVE reindexar quando novo documento for adicionado
- DEVE extrair frontmatter (score, tags) e conteúdo separadamente
- DEVE suportar indexação incremental (só arquivos novos/modificados)

### Score de reforço
- DEVE armazenar mapeamento `message_id → documento_fonte` para rastrear qual doc gerou qual resposta
- DEVE incrementar score do documento quando reação 👍 for recebida
- DEVE decrementar score quando reação 👎 for recebida
- DEVE usar score como fator de boost no ranking de busca (não como filtro)
- Score DEVE ser persistido no frontmatter do .md (campo `score`)

### Interface plugável
- DEVE definir ABC `KnowledgeBackend` com métodos: `index()`, `search()`, `reindex()`
- DEVE ter implementação `FTS5Backend` como padrão (zero dependências)
- DEVE ter implementação `QmdBackend` como opcional (requer qmd instalado)
- DEVE detectar automaticamente se qmd está disponível no PATH

## Requisitos Não-Funcionais
- Busca DEVE retornar em menos de 500ms para bases com até 1000 documentos
- Índice FTS5 DEVE ser armazenado em `knowledge/knowledge.db`
- DEVE ser resiliente a documentos mal formatados (sem frontmatter, encoding errado)

## Formato do documento

```markdown
---
score: 5
tags: [vpn, rede, forticlient]
created: 2026-03-18
source: atendimento
used_count: 12
---

# VPN não conecta após atualização

## Problema
Usuário reporta que VPN parou...

## Solução
1. Reiniciar serviço FortiClient
...
```

## Cenários

### Busca com resultado
```
Input: "VPN não funciona"
Output: [
  { path: "atendimentos/vpn-nao-conecta.md", score: 5, snippet: "Reiniciar serviço FortiClient..." },
  { path: "documentacao/sistemas/vpn-configuracao.md", score: 0, snippet: "Guia de configuração..." }
]
```

### Busca sem resultado
```
Input: "impressora não liga"
Output: []
→ Atendente sabe que é um caso novo, tenta resolver do zero
```

### Reforço positivo
```
Evento: reaction 👍 na msg_id 12345
Mapeamento: msg_id 12345 → atendimentos/vpn-nao-conecta.md
Ação: score de 5 → 6 no frontmatter do .md
```
