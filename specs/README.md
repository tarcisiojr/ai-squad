# Contratos e Especificações

Diretório guarda-chuva para submodulos git dos repositórios do projeto.

## Estrutura

Cada submodulo deve conter:
- `openapi.yaml` - Contrato de API REST
- `asyncapi.yaml` - Contrato de eventos assíncronos (quando aplicável)
- `schemas/` - Schemas de dados compartilhados

## Workflow de Criação de Contratos

1. **PO especifica** - O agente PO cria a especificação da feature
2. **PO commita contrato** - Antes do desenvolvimento, contratos são commitados no submodulo
3. **Dev implementa** - Subagentes implementam respeitando os contratos
4. **CI valida** - O CI verifica que PRs não quebram contratos existentes

## Adicionando um Submodulo

```bash
# Adiciona novo submodulo
git submodule add <url-do-repo> specs/<nome-do-repo>

# Cria estrutura base no submodulo
cd specs/<nome-do-repo>
mkdir -p schemas
touch openapi.yaml asyncapi.yaml
```

## Validação de Contratos no CI

PRs que alteram endpoints ou schemas devem:
1. Manter compatibilidade retroativa com contratos existentes
2. Atualizar contratos quando necessário (com aprovação do PO)
3. Nunca remover campos obrigatórios sem deprecação
