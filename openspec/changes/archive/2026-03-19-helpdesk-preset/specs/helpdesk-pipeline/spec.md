# Spec: Helpdesk Pipeline

## Descrição
Pipeline declarativo para atendimento de chamados com busca em knowledge base, escalação e registro de soluções.

## Requisitos Funcionais

### Pipeline
- DEVE definir pipeline com 4 steps: busca-kb → atendimento → escalação → registro
- Step busca-kb: execution `inline`, model_tier `fast` — busca rápida na KB
- Step atendimento: execution `subagent`, model_tier `powerful` — responde ao usuário
- Step escalação: type `checkpoint` — pausa para humano quando agente não resolve
- Step registro: execution `inline`, model_tier `fast` — salva solução na KB

### Squad Lead especializado
- DEVE classificar mensagens: chamado vs ingestão de documento vs status
- Se chamado → inicia pipeline de atendimento
- Se documento/arquivo → delega ao agente base-conhecimento
- Se status → responde com métricas simples (chamados resolvidos, docs na base)
- DEVE gerenciar escalação: quando Atendente não resolve, checkpoint para humano

### Agente Atendente
- DEVE receber o chamado + contexto da KB (se encontrado)
- DEVE formular resposta baseada nos documentos encontrados
- DEVE registrar qual documento usou (para tracking de reação)
- Se resolveu algo novo (sem doc na KB) → salva solução como novo .md
- DEVE aceitar texto, fotos, voz como entrada
- DEVE responder de forma clara e objetiva (suporte interno, tom profissional)

### Agente Base Conhecimento
- DEVE receber arquivos enviados pelo Telegram (PDF, DOCX, MD, imagem, texto)
- DEVE converter para Markdown estruturado
- DEVE indexar na knowledge base
- DEVE fazer git commit
- DEVE confirmar ao usuário que documento foi indexado

### Escalação
- Quando Atendente não encontra solução na KB E não consegue resolver
- DEVE notificar: "Não encontrei solução para esse caso. Encaminhando para atendimento humano."
- Checkpoint pausa até humano resolver
- Após humano resolver, Atendente registra a solução na KB

## Estrutura do preset

```
src/presets/helpdesk/
├── pipeline/
│   ├── pipeline.yaml
│   └── steps/
│       ├── step-01-busca-kb.md
│       ├── step-02-atendimento.md
│       ├── step-03-escalacao.md
│       └── step-04-registro.md
├── agents/
│   ├── squad-lead/AGENTS.md
│   ├── atendente/AGENTS.md
│   └── base-conhecimento/AGENTS.md
└── knowledge/
    ├── atendimentos/
    └── documentacao/
        ├── sistemas/
        ├── processos/
        └── faq/
```

## Cenários

### Chamado com solução na KB
```
Usuário: "Minha VPN não conecta"
1. Squad Lead classifica: CHAMADO
2. Busca KB: encontra vpn-nao-conecta.md (score: 7)
3. Atendente responde com a solução do documento
4. Registra mapeamento msg_id → doc para tracking de reação
5. Usuário reage 👍 → score 7 → 8
```

### Chamado sem solução na KB
```
Usuário: "Impressora do 3º andar não imprime"
1. Squad Lead classifica: CHAMADO
2. Busca KB: nenhum resultado relevante
3. Atendente tenta resolver (pede mais detalhes, sugere diagnóstico)
4a. Se resolver → salva knowledge/atendimentos/impressora-3-andar.md + indexa
4b. Se não resolver → escalação (checkpoint humano)
5. Humano resolve → Atendente registra solução na KB
```

### Ingestão de documento
```
Usuário envia: manual-crm.pdf "Adiciona na base"
1. Squad Lead classifica: INGESTÃO
2. Delega ao agente base-conhecimento
3. Agente converte PDF → MD, salva, indexa, commita
4. Responde: "Manual do CRM indexado! 12 seções sobre módulos do sistema."
```

### Escalação
```
Usuário: "O servidor caiu"
1. Busca KB: nada relevante
2. Atendente: "Não tenho informações sobre esse caso. Vou encaminhar para atendimento humano."
3. Checkpoint: aguarda humano
4. Humano resolve e informa a solução
5. Atendente registra: knowledge/atendimentos/servidor-caiu-2026-03-18.md
```
