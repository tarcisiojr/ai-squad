# agno-tools-config

## Purpose

Configuração declarativa de toolkits Agno (web search, code execution, shell) por agente via config.yaml. Permite que cada agente tenha ferramentas extras além das MCP tools do AI Squad.

## Requirements

### Requirement: Campo tools no config.yaml
O config.yaml SHALL suportar campo opcional `tools` na configuração de cada agente. O campo aceita lista de toolkits habilitados. Toolkits disponíveis: `web_search`, `code_execution`, `shell`.

#### Scenario: Agente com web search habilitado
- **GIVEN** config.yaml com:
  ```yaml
  agents:
    pesquisador:
      name: "Pesquisador"
      tools:
        - web_search
  ```
- **WHEN** o adapter Agno cria o agente "pesquisador"
- **THEN** `DuckDuckGoTools()` é adicionado às tools do agente

#### Scenario: Agente sem tools extras
- **GIVEN** config.yaml sem campo `tools` em um agente
- **WHEN** o adapter Agno cria o agente
- **THEN** apenas as MCP tools do AI Squad são disponibilizadas

#### Scenario: Agente com múltiplas tools
- **GIVEN** config.yaml com `tools: [web_search, code_execution, shell]`
- **WHEN** o adapter Agno cria o agente
- **THEN** `DuckDuckGoTools()`, `PythonTools()` e `ShellTools()` são adicionados às tools

### Requirement: Configuração de web search
O toolkit `web_search` SHALL usar DuckDuckGo como provider padrão (gratuito, sem API key). SHALL suportar configuração opcional de provider alternativo via campo `web_search_provider` (duckduckgo, tavily, serpapi).

#### Scenario: Web search padrão (DuckDuckGo)
- **WHEN** `tools: [web_search]` sem provider especificado
- **THEN** o adapter usa `DuckDuckGoTools()` (zero config)

#### Scenario: Web search com Tavily
- **GIVEN** config.yaml com:
  ```yaml
  agents:
    pesquisador:
      tools:
        - web_search
      web_search_provider: tavily
  ```
- **WHEN** o adapter cria o agente
- **THEN** usa `TavilyTools()` (requer TAVILY_API_KEY no .env)

### Requirement: Configuração de code execution
O toolkit `code_execution` SHALL usar `PythonTools` do Agno com sandbox em diretório temporário. SHALL NOT permitir `pip_install` por padrão (segurança). O diretório base SHALL ser configurável.

#### Scenario: Code execution padrão
- **WHEN** `tools: [code_execution]` sem configuração extra
- **THEN** o adapter usa `PythonTools(base_dir="/tmp/ai-squad-sandbox", pip_install=False)`

### Requirement: Configuração de shell
O toolkit `shell` SHALL usar `ShellTools` do Agno com diretório base sendo o working_dir do adapter. SHALL respeitar o mesmo diretório de trabalho dos agentes.

#### Scenario: Shell tools com working dir
- **WHEN** `tools: [shell]` e working_dir é `/workspace/projeto`
- **THEN** o adapter usa `ShellTools(base_dir="/workspace/projeto")`

### Requirement: Compatibilidade com ClaudeAgentSDKAdapter
O campo `tools` SHALL ser ignorado silenciosamente quando o provider é `claude-agent-sdk`. Isto garante que o mesmo config.yaml funcione com ambos os providers sem erro.

#### Scenario: Campo tools com provider Claude
- **WHEN** config.yaml tem `ai_provider: claude-agent-sdk` e um agente com `tools: [web_search]`
- **THEN** o sistema inicia normalmente, ignorando o campo tools (Claude SDK usa suas próprias tools)
