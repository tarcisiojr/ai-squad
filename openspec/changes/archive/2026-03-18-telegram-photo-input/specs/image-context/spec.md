## ADDED Requirements

### Requirement: Engine aceita imagem como contexto
O OrchestrationEngine SHALL aceitar imagem no run_squad_lead e passá-la ao adapter como contexto multimodal.

#### Scenario: Squad Lead recebe imagem
- **WHEN** daemon chama run_squad_lead com image_path
- **THEN** engine SHALL incluir imagem no contexto passado ao adapter
- **THEN** Squad Lead SHALL conseguir analisar o conteúdo da imagem

#### Scenario: Sem imagem (comportamento atual)
- **WHEN** daemon chama run_squad_lead sem image_path
- **THEN** engine SHALL funcionar normalmente (sem mudança)

### Requirement: Adapter passa imagem como content block multimodal
O ClaudeAgentSDKAdapter SHALL montar prompt com content blocks multimodal quando imagem está presente.

#### Scenario: Prompt com imagem
- **WHEN** adapter recebe contexto com image_path
- **THEN** SHALL ler a imagem e converter para base64
- **THEN** SHALL montar prompt como lista de content blocks (image + text)

#### Scenario: Prompt sem imagem
- **WHEN** adapter recebe contexto sem image_path
- **THEN** SHALL montar prompt como texto simples (comportamento atual)
