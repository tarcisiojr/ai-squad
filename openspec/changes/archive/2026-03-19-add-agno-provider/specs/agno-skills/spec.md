# agno-skills

## Purpose

Carregamento de skills no AgnoAdapter com compatibilidade retroativa com AGENTS.md existentes. Suporta os 3 níveis de skills do AI Squad (projeto, agente, globais) usando o sistema nativo de Skills do Agno com progressive discovery.

## Requirements

### Requirement: Fallback AGENTS.md → instruction
O adapter SHALL verificar, para cada diretório de skills, se existe `SKILL.md` (formato Agno nativo). Se NÃO existir mas existir `AGENTS.md`, o adapter SHALL ler o conteúdo do `AGENTS.md` e injetá-lo como `instruction` do agente Agno. Isto garante zero mudança nos presets existentes.

#### Scenario: Diretório com SKILL.md (Agno nativo)
- **GIVEN** diretório `/app/agents/po/` contém `SKILL.md` com frontmatter válido
- **WHEN** o adapter cria o agente "po"
- **THEN** usa `LocalSkills("/app/agents/po/")` para carregar a skill nativamente

#### Scenario: Diretório com AGENTS.md (legado)
- **GIVEN** diretório `/app/agents/po/` contém `AGENTS.md` mas NÃO `SKILL.md`
- **WHEN** o adapter cria o agente "po"
- **THEN** lê o conteúdo de `AGENTS.md` e injeta como `instruction` do agente Agno

#### Scenario: Diretório com ambos
- **GIVEN** diretório contém tanto `SKILL.md` quanto `AGENTS.md`
- **WHEN** o adapter cria o agente
- **THEN** prioriza `SKILL.md` (Agno nativo) e ignora `AGENTS.md`

### Requirement: 3 níveis de skills
O adapter SHALL carregar skills dos 3 níveis, na mesma ordem de prioridade do ClaudeAgentSDKAdapter:
1. **Agente**: `agents_dir/<agent_name>/` — skills específicas do agente
2. **Globais**: `global_skills_dir/` — skills compartilhadas pelo time
3. **Projeto**: `working_dir/.claude/skills/` — skills do projeto sendo trabalhado

#### Scenario: Skills dos 3 níveis carregadas
- **GIVEN** existem skills em `/app/agents/dev/`, `/app/global-skills/` e `/workspace/.claude/skills/`
- **WHEN** o adapter cria o agente "dev"
- **THEN** o agente tem acesso a skills dos 3 diretórios via `Skills(loaders=[...])`

#### Scenario: Diretório inexistente ignorado
- **GIVEN** `global_skills_dir` aponta para diretório que não existe
- **WHEN** o adapter cria o agente
- **THEN** o loader é omitido silenciosamente (sem erro)

### Requirement: Progressive discovery
Quando skills são carregadas via `SKILL.md` nativo, o agente SHALL usar o progressive discovery do Agno: summaries no system prompt, carregamento completo sob demanda via tools (`get_skill_instructions`, `get_skill_reference`, `get_skill_script`).

#### Scenario: Agente carrega skill sob demanda
- **GIVEN** agente tem 5 skills disponíveis via SKILL.md
- **WHEN** o agente precisa de instruções de uma skill específica
- **THEN** chama `get_skill_instructions(skill_name)` e recebe o conteúdo completo

#### Scenario: Fallback AGENTS.md não usa progressive discovery
- **GIVEN** agente tem skill via AGENTS.md (fallback)
- **WHEN** o agente é criado
- **THEN** o conteúdo do AGENTS.md é injetado diretamente como instruction (sem lazy loading)

### Requirement: Compatibilidade com ClaudeAgentSDKAdapter
O campo `skills` e o sistema de SKILL.md SHALL ser ignorados pelo `ClaudeAgentSDKAdapter`. O adapter Claude continua usando `add_dirs` com AGENTS.md. Os dois sistemas coexistem sem conflito.

#### Scenario: Mesmo preset com ambos os providers
- **GIVEN** preset `dev-openspec` com AGENTS.md nos diretórios de agentes
- **WHEN** usado com `ai_provider: claude-agent-sdk`
- **THEN** funciona via `add_dirs` como antes
- **WHEN** usado com `ai_provider: agno`
- **THEN** funciona via fallback AGENTS.md → instruction
