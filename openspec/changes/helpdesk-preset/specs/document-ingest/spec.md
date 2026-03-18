# Spec: Document Ingest

## Descrição
Pipeline de conversão de documentos recebidos pelo Telegram para Markdown indexável na knowledge base.

## Requisitos Funcionais

### Formatos suportados
- DEVE converter PDF → Markdown (extração de texto com pdfplumber)
- DEVE converter DOCX → Markdown (python-docx + conversão)
- DEVE aceitar Markdown direto (apenas copia e indexa)
- DEVE aceitar texto puro (estrutura em .md com título inferido)
- DEVE aceitar imagens (gera descrição via LLM e salva como .md)

### Processo de ingestão
- DEVE receber arquivo do Telegram (via handler de document)
- DEVE detectar tipo do arquivo pela extensão e MIME type
- DEVE converter para Markdown com estrutura legível
- DEVE gerar slug para nome do arquivo (ex: "Manual do ERP" → `manual-do-erp.md`)
- DEVE salvar em `knowledge/documentacao/` com subpasta por categoria (se informada)
- DEVE adicionar frontmatter com metadados (source, created, original_filename)
- DEVE indexar no knowledge store após salvar
- DEVE fazer git commit com mensagem descritiva

### Classificação
- DEVE perguntar ao usuário a categoria quando não for óbvia (ou inferir do conteúdo)
- Categorias padrão: `sistemas/`, `processos/`, `faq/`
- DEVE permitir categorias customizadas

### Feedback
- DEVE informar o usuário quando ingestão concluir: "Documento indexado! Agora posso responder sobre isso."
- DEVE informar erro se conversão falhar: "Não consegui processar esse arquivo. Tente em outro formato."

## Requisitos Não-Funcionais
- DEVE processar documentos de até 50 páginas (PDF)
- Tempo de ingestão: menos de 30s para PDFs de 10 páginas
- DEVE ser resiliente a PDFs com imagens (extrai texto disponível, ignora imagens)

## Cenários

### PDF recebido pelo Telegram
```
Usuário envia: manual-erp-v3.pdf
Caption: "Manual do ERP, pode adicionar?"

Agente base-conhecimento:
1. Baixa o PDF do Telegram
2. Extrai texto com pdfplumber
3. Estrutura em Markdown (headings, parágrafos, tabelas)
4. Salva em knowledge/documentacao/sistemas/manual-erp-v3.md
5. Frontmatter: { source: "pdf", created: "2026-03-18", original: "manual-erp-v3.pdf", score: 0 }
6. Indexa no knowledge store
7. git commit -m "docs: manual-erp-v3.md (PDF importado)"
8. Responde: "Manual do ERP indexado! São 15 seções sobre módulos do sistema."
```

### Imagem com texto (screenshot)
```
Usuário envia: foto de tela de erro
Caption: "Esse erro aparece quando tenta acessar o CRM"

Agente base-conhecimento:
1. Baixa imagem
2. Envia ao LLM para descrição: "Tela de erro 403 Forbidden no CRM..."
3. Salva como knowledge/documentacao/faq/erro-403-crm.md
4. Responde: "Screenshot de erro 403 no CRM registrado."
```

### Markdown direto
```
Usuário envia: processo-onboarding.md
Caption: "Processo de onboarding"

Agente base-conhecimento:
1. Copia para knowledge/documentacao/processos/processo-onboarding.md
2. Adiciona frontmatter se não tiver
3. Indexa e commita
4. Responde: "Processo de onboarding adicionado à base."
```
