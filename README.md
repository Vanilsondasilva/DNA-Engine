# DNA Engine — Documentação Completa

> **Versão:** 1.0 | **Plataforma:** Snowflake Streamlit (Snowpark) | **Idioma:** Português

---

## Sumário

1. [Visão Geral do Projeto](#1-visão-geral-do-projeto)
2. [Arquitetura da Solução](#2-arquitetura-da-solução)
3. [Modelo de Dados](#3-modelo-de-dados)
4. [Configuração e Instalação](#4-configuração-e-instalação)
5. [Fluxo Geral da Aplicação](#5-fluxo-geral-da-aplicação)
6. [Aba 1 — Criar Nova Regra](#6-aba-1--criar-nova-regra)
   - 6.1 [Regra Simples](#61-regra-simples)
   - 6.2 [Regra Composta](#62-regra-composta)
7. [Aba 2 — Gestão do Dicionário](#7-aba-2--gestão-do-dicionário)
8. [Aba 3 — Processamento Global (Sala de Controle)](#8-aba-3--processamento-global-sala-de-controle)
   - 8.1 [Motor Fase 1 — Regras Simples](#81-motor-fase-1--regras-simples)
   - 8.2 [Motor Fase 2 — Regras Compostas](#82-motor-fase-2--regras-compostas)
9. [Aba 4 — Auditoria de Regras](#9-aba-4--auditoria-de-regras)
10. [Aba 5 — Visualizar Base](#10-aba-5--visualizar-base)
11. [Referência Técnica das Funções](#11-referência-técnica-das-funções)
12. [Glossário](#12-glossário)
13. [Guia do Operador (Usuário Final)](#13-guia-do-operador-usuário-final)
14. [Guia do Desenvolvedor](#14-guia-do-desenvolvedor)

---

## 1. Visão Geral do Projeto

O **DNA Engine** é uma aplicação de inteligência analítica em saúde, construída inteiramente dentro do **Snowflake** usando **Streamlit** e **Snowpark Python**. Seu objetivo é transformar dados brutos de produção assistencial (consultas, exames, procedimentos) em uma **Matriz DNA** — uma tabela estruturada onde cada linha representa um beneficiário e cada coluna `FL_*` representa uma inteligência (flag) que indica se aquele indivíduo atende a determinado critério clínico ou comportamental.

### Propósito Principal

| Quem usa | Para quê |
|---|---|
| **Analistas de Saúde / Gestores** | Configurar e gerenciar as regras de inteligência (flags) sem escrever SQL. |
| **Equipes de Jornada do Paciente** | Identificar populações específicas para ações preventivas, de engajamento ou de gestão de crônicos. |
| **Equipes Técnicas / DBA** | Acompanhar o processamento, auditar as flags e garantir a qualidade dos dados na tabela Gold. |

### Conceito-Chave: A Tabela DNA

```
TB_DNA (GOLD)
┌─────────────┬──────────────┬───────┬──────────────────────┬─────────────────────┬─────────┐
│  ID_PESSOA  │ DT_NASCIMENTO│ IDADE │ FL_TRATAMENTO_ONCO   │ FL_RASTREIO_RENAL   │  ...    │
├─────────────┼──────────────┼───────┼──────────────────────┼─────────────────────┼─────────┤
│  12345      │  1975-03-10  │  49   │          1           │          0          │  ...    │
│  67890      │  1988-11-22  │  35   │          0           │          1          │  ...    │
└─────────────┴──────────────┴───────┴──────────────────────┴─────────────────────┴─────────┘
```

Cada coluna `FL_*` é criada **dinamicamente** pelo motor Python quando uma nova regra é cadastrada. O valor `1` significa que o critério foi satisfeito; `0` significa que não foi.

---

## 2. Arquitetura da Solução

### Visão em Camadas (Medallion Architecture)

```mermaid
graph TB
    subgraph BRONZE["🟤 BRONZE — FEDERACAO.BRONZE"]
        FP["FATOPRODUCAO\n(Tabela Fato de Produção)"]
        USR["USUARIOS\n(Dim. de Beneficiários)"]
    end

    subgraph SILVER["🥈 SILVER — DB_GESTAO_SAUDE.SILVER"]
        DIC["TB_DICIONARIO_REGRAS\n(Regras Simples)"]
        DICC["TB_DICIONARIO_COMPOSTO\n(Regras Compostas)"]
    end

    subgraph GOLD["🥇 GOLD — DB_GESTAO_SAUDE.GOLD"]
        DNA["TB_DNA\n(Matriz Analítica Final)"]
    end

    subgraph APP["📱 DNA Engine — Streamlit App"]
        T1["Aba 1: Criar Nova Regra"]
        T2["Aba 2: Gestão do Dicionário"]
        T3["Aba 3: Processamento Global"]
        T4["Aba 4: Auditoria de Regras"]
        T5["Aba 5: Visualizar Base"]
    end

    FP --> T3
    USR --> T3
    T1 -->|INSERT| DIC
    T1 -->|INSERT| DICC
    T2 -->|UPDATE/DELETE| DIC
    T3 -->|Lê regras| DIC
    T3 -->|Lê regras| DICC
    T3 -->|Lê dados| FP
    T3 -->|Lê dados| USR
    T3 -->|ESCREVE FLAGS| DNA
    T4 -->|Lê| DNA
    T4 -->|Valida contra| FP
    T5 -->|Lê preview| DNA
```

### Estrutura de Arquivos

```
app/
├── streamlit_app.py            # Orquestrador principal — monta as 5 abas
├── config.py                   # Centralização de nomes de banco/schema/tabela
├── funcoes_execucao_regras.py  # Aba 1: Formulário de criação de regras
├── funcoes_gestao_dicionario.py# Aba 2: Editor e exclusão de regras
├── funcoes_gestao_total_dna.py # Aba 3 + Motores de Processamento (Fase 1 e 2)
├── funcoes_auditoria_regras.py # Aba 4: Auditoria paciente × regra
├── funcoes_visualizacao_dados.py# Aba 5: Preview da tabela Gold
├── setup_banco_dna.sql         # Script DDL para criação das tabelas
├── setup_infraestrutura_dna.sql# Stored Procedures legadas (referência histórica)
└── environment.yml             # Dependências Python do ambiente Snowflake

scripts/
├── pipeline_risco_mama_v3.py   # Pipeline de risco mama v3 com score e flags inferidas
├── clinical_chain_detector.py  # Inferência de cadeias clínicas temporais
└── __init__.py                 # Permite importação do diretório como pacote
```

---

## Pipeline adicional — Risco Mama

O repositório também inclui `scripts/pipeline_risco_mama_v3.py`, um pipeline específico para risco mama, apoiado pelo módulo `scripts/clinical_chain_detector.py`.

As novas flags inferidas por cadeia temporal são:

- `MAMOGRAFIA_RESULTADO_INFERIDO_ALTERADO`
- `BRCA_POSITIVO_INFERIDO`
- `CADEIA_INVESTIGACAO_ONCOLOGICA`
- `INVESTIGACAO_POS_BRCA`
- `PARTO_PRIMIPARO_APOS_30`

Os pesos dessas flags podem ser agregados ao score final via configuração do pipeline.

---

## 3. Modelo de Dados

### 3.1 Diagrama Entidade-Relacionamento (ERD)

```mermaid
erDiagram
    TB_DICIONARIO_REGRAS {
        varchar CATEGORIA PK "Nome único da flag (ex: TRATAMENTO_ONCO_ATIVO)"
        varchar PADRAO_REGEX "Expressão regular de busca"
        varchar TIPO_REGRA "VIGENCIA | FREQUENCIA | VOLUME"
        varchar PERIODICIDADE "MENSAL | TRIMESTRAL | SEMESTRAL | ANUAL (só para FREQUENCIA)"
        integer LIMIAR_VOLUME "Mínimo de guias distintas (só para VOLUME)"
        varchar COLUNA_ALVO "Colunas da tabela fato a serem pesquisadas"
        float MES_INICIO "Início da janela retroativa (ex: 0 = mês atual)"
        float MESES_RETROATIVOS "Fim da janela retroativa (ex: 12 = 12 meses atrás)"
        varchar SEXO_ALVO "Ambos | M | F"
        float IDADE_MIN "Idade mínima do filtro"
        float IDADE_MAX "Idade máxima do filtro"
        varchar DESCRICAO "Registro interno automático"
        varchar NARRATIVA_CLINICA "Texto clínico legível para jornada"
        varchar CONTEXTO_TECNICO "Grupo/especialidade (ex: ONCOLOGIA)"
        timestamp DT_CRIACAO
        timestamp DT_ATUALIZACAO
    }

    TB_DICIONARIO_COMPOSTO {
        varchar CATEGORIA_COMPOSTA PK "Nome da flag composta"
        varchar REGRAS_OBRIGATORIAS "Flags que DEVEM existir (AND)"
        varchar REGRAS_ALTERNATIVAS "Flags onde ao menos UMA deve existir (OR)"
        varchar REGRAS_EXCLUSAO "Flags que, se existirem, excluem o paciente (NOT)"
        integer JANELA_COOCORRENCIA_DIAS "Dias max entre eventos (0 = mesma guia)"
        integer EXIGE_ORDEM_CRONOLOGICA "1 = obrigatório antes do alternativo"
        float MES_INICIO
        float MESES_RETROATIVOS
        varchar SEXO_ALVO
        float IDADE_MIN
        float IDADE_MAX
        varchar CONTEXTO_TECNICO
        varchar NARRATIVA_CLINICA
        integer FL_ATIVO "1 = ativa | 0 = inativa"
        timestamp DT_CRIACAO
        timestamp DT_ATUALIZACAO
    }

    TB_DNA {
        varchar ID_PESSOA PK "Identificador único do beneficiário"
        date DT_NASCIMENTO
        integer IDADE
        integer FL_XXXX "Flags criadas dinamicamente (0 ou 1)"
    }

    FATOPRODUCAO {
        varchar ID_USUARIO FK
        varchar NUMERO_GUIA
        varchar DATA_ATENDIMENTO_FATO_PRO
        varchar SERVICO
        varchar GRUPO_ASSISTENCIAL
        varchar SUBGR_SERVICO
        varchar CODIGO_SERVICO
        varchar CODIGO_CID
    }

    USUARIOS {
        varchar ID_USUARIO PK
        varchar ID_PESSOA FK
        varchar USUARIO "Nome"
        varchar SEXO
        integer IDADE
        date DT_NASCIMENTO
    }

    FATOPRODUCAO }|--|| USUARIOS : "ID_USUARIO"
    USUARIOS ||--o| TB_DNA : "ID_PESSOA"
    TB_DICIONARIO_REGRAS ||--o{ TB_DNA : "gera colunas FL_*"
    TB_DICIONARIO_COMPOSTO ||--o{ TB_DNA : "gera colunas FL_* compostas"
    TB_DICIONARIO_COMPOSTO }o--o{ TB_DICIONARIO_REGRAS : "referencia por CATEGORIA"
```

### 3.2 Descrição das Tabelas

#### `TB_DICIONARIO_REGRAS` (Silver)
Armazena cada **regra simples** — a unidade básica de inteligência. Cada linha define:
- **O quê buscar** (`PADRAO_REGEX` aplicado em `COLUNA_ALVO`)
- **Quando buscar** (janela de meses retroativos: `MES_INICIO` → `MESES_RETROATIVOS`)
- **Para quem** (filtros de `SEXO_ALVO`, `IDADE_MIN`, `IDADE_MAX`)
- **Como classificar** (`TIPO_REGRA`: vigência, frequência ou volume)

#### `TB_DICIONARIO_COMPOSTO` (Silver)
Armazena **protocolos clínicos** — combinações lógicas de regras simples:
- **AND**: todas as regras obrigatórias devem estar presentes
- **OR**: pelo menos uma das regras alternativas deve estar presente
- **NOT**: a regra de exclusão não pode existir
- **Co-ocorrência**: os eventos podem ter que ocorrer dentro de uma janela de dias

#### `TB_DNA` (Gold)
A tabela de saída final. Começa com apenas 3 colunas (`ID_PESSOA`, `DT_NASCIMENTO`, `IDADE`) e **cresce automaticamente** com colunas `FL_*` conforme novas regras são cadastradas e processadas.

---

## 4. Configuração e Instalação

### 4.1 Pré-requisitos

- Conta Snowflake ativa com permissões de criação de objetos
- Snowflake Streamlit habilitado (Snowpark Container Services ou Streamlit in Snowflake)
- Bancos de dados `DB_GESTAO_SAUDE` e `FEDERACAO` criados

### 4.2 Diagrama de Setup Inicial

```mermaid
flowchart TD
    A([Início]) --> B[Executar setup_banco_dna.sql]
    B --> C{Banco e schemas\nexistem?}
    C -->|Não| D[Criar DB_GESTAO_SAUDE\ncom schemas SILVER e GOLD]
    D --> E
    C -->|Sim| E[Criar TB_DICIONARIO_REGRAS]
    E --> F[Criar TB_DICIONARIO_COMPOSTO]
    F --> G[Criar TB_DNA com colunas base]
    G --> H[Executar INSERT inicial:\nCarregar beneficiários na TB_DNA\na partir de USUARIOS]
    H --> I[Configurar config.py\ncom os nomes corretos\nde banco/schema/tabela]
    I --> J[Fazer upload dos arquivos .py\npara o Streamlit in Snowflake]
    J --> K[Configurar environment.yml\ncomo dependências do app]
    K --> L([Aplicação pronta para uso ✅])
```

### 4.3 Adaptação do `config.py`

Ao mudar de ambiente (Dev → Prod) ou de cliente, edite **apenas** o arquivo `config.py`:

```python
# Exemplo de adaptação para novo cliente:
DATABASE = "DB_CLIENTE_XYZ"          # ← altere aqui
SCHEMA_SILVER = f"{DATABASE}.SILVER"
SCHEMA_GOLD   = f"{DATABASE}.GOLD"

DATABASE_FEDERACAO = "FEDERACAO_XYZ"  # ← altere aqui
SCHEMA_BRONZE_FEDERACAO = f"{DATABASE_FEDERACAO}.BRONZE"
```

> **Regra de ouro:** Nenhum outro arquivo Python precisa ser alterado ao trocar de ambiente. Todo o mapeamento está centralizado em `config.py`.

### 4.4 Variáveis de Configuração

| Variável | Valor Padrão | Descrição |
|---|---|---|
| `DATABASE` | `DB_GESTAO_SAUDE` | Banco principal de saúde |
| `SCHEMA_SILVER` | `DB_GESTAO_SAUDE.SILVER` | Camada Silver (dicionários) |
| `SCHEMA_GOLD` | `DB_GESTAO_SAUDE.GOLD` | Camada Gold (tabela DNA final) |
| `DATABASE_FEDERACAO` | `FEDERACAO` | Banco de origem dos dados brutos |
| `SCHEMA_BRONZE_FEDERACAO` | `FEDERACAO.BRONZE` | Camada Bronze (dados crus) |
| `TABELA_FATO_PRODUCAO` | `FEDERACAO.BRONZE.FATOPRODUCAO` | Tabela fato de produção assistencial |
| `TABELA_DIM_USUARIO` | `FEDERACAO.BRONZE.USUARIOS` | Dimensão de beneficiários |
| `TABELA_DICIONARIO` | `DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS` | Regras simples |
| `TABELA_DICIONARIO_COMPOSTO` | `DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_COMPOSTO` | Regras compostas |
| `TABELA_DNA` | `DB_GESTAO_SAUDE.GOLD.TB_DNA` | Matriz DNA final |
| `DATA_ATENDIMENTO` | `TRY_TO_DATE(DATA_ATENDIMENTO_FATO_PRO, 'DD/MM/YYYY')` | Expressão SQL da data de atendimento |

---

## 5. Fluxo Geral da Aplicação

### 5.1 Navegação Principal

```mermaid
flowchart TD
    START([Usuário acessa o app]) --> CONN{Conexão Snowflake\nativa via get_active_session}
    CONN -->|Falha| ERR[❌ Exibe erro de conexão\nst.stop]
    CONN -->|Sucesso| TABS[Interface com 5 Abas]

    TABS --> T1["📋 Aba 1\nCriar Nova Regra"]
    TABS --> T2["📖 Aba 2\nGestão do Dicionário"]
    TABS --> T3["⚙️ Aba 3\nProcessamento Global"]
    TABS --> T4["🔎 Aba 4\nAuditoria de Regras"]
    TABS --> T5["👁️ Aba 5\nVisualizar Base"]

    T1 -->|"render_aba_execucao(session)"| M1[funcoes_execucao_regras.py]
    T2 -->|"render_aba_dicionario(session)"| M2[funcoes_gestao_dicionario.py]
    T3 -->|"render_aba_gestao_total(session)"| M3[funcoes_gestao_total_dna.py]
    T4 -->|"render_aba_auditoria(session)"| M4[funcoes_auditoria_regras.py]
    T5 -->|"render_aba_visualizacao(session)"| M5[funcoes_visualizacao_dados.py]
```

### 5.2 Ciclo de Vida Completo de uma Regra

```mermaid
sequenceDiagram
    actor Analista
    participant App as DNA Engine (Streamlit)
    participant DIC as TB_DICIONARIO_REGRAS (Silver)
    participant FATO as FATOPRODUCAO (Bronze)
    participant DNA as TB_DNA (Gold)

    Analista->>App: Preenche formulário de nova regra (Aba 1)
    App->>DIC: INSERT — salva a regra no dicionário
    App->>App: Chama reprocessar_dna_motor_python(categoria_alvo=NOVA_REGRA)
    App->>DNA: ALTER TABLE — ADD COLUMN IF NOT EXISTS FL_NOVA_REGRA
    App->>DNA: UPDATE — zera a coluna FL_NOVA_REGRA = 0
    App->>FATO: SELECT — aplica regex + filtros de tempo + bio-perfil
    FATO-->>App: Retorna IDs de beneficiários que satisfazem a regra
    App->>DNA: UPDATE — seta FL_NOVA_REGRA = 1 para os IDs encontrados
    App-->>Analista: ✅ Sucesso! Regra processada.

    Note over Analista,DNA: Quando necessário (reprocessamento em lote)
    Analista->>App: Acessa Aba 3 e confirma "Processamento Global"
    App->>DIC: SELECT * — carrega todas as regras
    App->>DNA: ALTER TABLE + UPDATE (todas as colunas FL_*)
    App->>FATO: SELECT — processa em single-pass (query única)
    App->>DNA: UPDATE em lote com todos os resultados
    App-->>Analista: ✅ Base DNA atualizada
```

---

## 6. Aba 1 — Criar Nova Regra

**Arquivo:** `funcoes_execucao_regras.py`  
**Função principal:** `render_aba_execucao(session)`

Esta aba permite ao analista criar inteligências (flags) que serão aplicadas sobre a base de dados. Há dois modos de criação: **Regra Simples** e **Regra Composta**.

### 6.1 Regra Simples

Uma Regra Simples detecta um **evento único** nos dados de produção, com base em expressões regulares (Regex), filtros de tempo e filtros de perfil biológico.

#### Tipos de Regra Simples

| Tipo | Lógica | Quando usar |
|---|---|---|
| **VIGENCIA** | Verifica se houve **ao menos um** evento dentro da janela de tempo | Detectar se o paciente fez algum procedimento no período |
| **FREQUENCIA** | Verifica se o evento ocorreu em **múltiplos períodos** (mensal/trimestral/semestral/anual) | Detectar uso contínuo de medicamentos, exames periódicos |
| **VOLUME** | Verifica se o número de guias distintas **atinge um limiar mínimo** | Detectar uso intenso de um serviço específico |

#### Fluxo de Criação de Regra Simples

```mermaid
flowchart TD
    A([Aba 1 aberta]) --> B[Carrega colunas da\nTABELA_FATO_PRODUCAO]
    B --> C[Usuário configura\nJanela de Vigência\nSlider: 0–48 meses]
    C --> D[Usuário configura\nBio-Perfil:\nSexo + Tipo + Periodicidade + Idade]
    D --> E[Usuário preenche\nFormulário Técnico:\nNome, Colunas, Regex, Contexto, Narrativa]
    E --> F[Clica: Salvar Regra e Criar Coluna na DNA]

    F --> G{Validação dos campos\nobrigatórios}
    G -->|Faltam campos| ERR1[❌ Exibe erro de validação]
    G -->|OK| H[INSERT na TB_DICIONARIO_REGRAS\ncom bind variables]

    H --> I[Chama\nreprocessar_dna_motor_python\ncategoria_alvo = NOVA_CATEGORIA]
    I --> J[Motor Python:\nALTER TABLE TB_DNA\nADD COLUMN IF NOT EXISTS FL_CATEGORIA]
    J --> K[Motor Python:\nUPDATE TB_DNA SET FL_CATEGORIA = 0]
    K --> L[Motor Python:\nMonta query mestra\ncom CASE WHEN + Regex + Filtros]
    L --> M[Motor Python:\nEXECUTA UPDATE TB_DNA\nconjunto com dados processados]
    M --> N{Resultado}
    N -->|Sucesso| OK[✅ st.success — Regra processada]
    N -->|Erro| ERR2[❌ st.error — detalhe técnico]
```

#### Campos do Formulário (Regra Simples)

| Campo | Obrigatório | Descrição |
|---|---|---|
| **Nome da Flag** (`CATEGORIA`) | ✅ | Identificador único. O sistema adiciona `FL_` automaticamente se não informado. Ex: `TRATAMENTO_ONCO_ATIVO` → coluna `FL_TRATAMENTO_ONCO_ATIVO` |
| **Janela de Vigência** | ✅ | Slider de 0 a 48 meses. Define o intervalo retroativo de busca. Ex: `(0, 3)` = últimos 3 meses. |
| **Sexo Alvo** | ✅ | `Ambos`, `M` ou `F` |
| **Tipo de Regra** | ✅ | `VIGENCIA`, `FREQUENCIA` ou `VOLUME` |
| **Periodicidade** | Condicional | Apenas para `FREQUENCIA`: `MENSAL`, `TRIMESTRAL`, `SEMESTRAL`, `ANUAL` |
| **Mínimo de Guias** | Condicional | Apenas para `VOLUME`: número inteiro ≥ 1 |
| **Filtro de Idade** | ✅ | `Sem Filtro`, `Idade Específica` ou `Faixa Etária` |
| **Colunas de Busca** | ✅ | Seleção múltipla das colunas da tabela fato onde o Regex será aplicado |
| **Padrão Regex** | ✅ | Expressão regular. Ex: `ONCOLOG\|QUIMIO\|RADIOTERAP` |
| **Contexto Técnico** | ✅ | Agrupador da regra. Ex: `ONCOLOGIA`, `CARDIOLOGIA` |
| **Narrativa Clínica** | ✅ | Texto humano que descreve o critério. Usado em jornadas do paciente |

### 6.2 Regra Composta

Uma Regra Composta (Protocolo Avançado) combina **múltiplas regras simples** usando lógica booleana, podendo exigir **co-ocorrência temporal** dos eventos.

#### Lógica do Protocolo

```
Resultado Final = (TODAS as Regras Obrigatórias [AND])
               E (PELO MENOS UMA Regra Alternativa [OR])
               E NÃO (NENHUMA Regra de Exclusão [NOT])
```

#### Fluxo de Criação de Regra Composta

```mermaid
flowchart TD
    A([Modo: Regra Composta selecionado]) --> B[Carrega lista de flags\nda TB_DICIONARIO_REGRAS]
    B --> C[Usuário define:\nRegras Obrigatórias AND\nRegras Alternativas OR\nRegras de Exclusão NOT]
    C --> D[Usuário configura:\nJanela Co-ocorrência em dias\nOrdem Cronológica?\nSexo + Idade + Janela Retroativa]
    D --> E[Usuário preenche:\nNome da Flag Composta\nContexto Técnico\nNarrativa Clínica]
    E --> F[Clica: Gravar Protocolo Composto]

    F --> G{Validação:\nNome e Contexto preenchidos?\nAo menos uma regra OR ou AND?}
    G -->|Falha| ERR[❌ Exibe erro]
    G -->|OK| H[INSERT na\nTB_DICIONARIO_COMPOSTO]
    H --> I[✅ Protocolo salvo!\n⚠️ Aviso: será processado\nna Sala de Controle - Fase 2]
```

> **Importante:** Ao salvar uma Regra Composta, ela é inserida no dicionário, mas o processamento (criação da coluna FL_* e atualização da TB_DNA) **só ocorre na Aba 3 — Processamento Global** (Motor Fase 2). Isso é diferente das Regras Simples, que são processadas imediatamente ao salvar.

#### Campos do Formulário (Regra Composta)

| Campo | Obrigatório | Descrição |
|---|---|---|
| **Obrigatório ter (AND)** | Condicional* | Flags que **todas** devem estar ativas. Pelo menos AND ou OR devem ser preenchidos |
| **Alternativo ter (OR)** | Condicional* | Flags onde **ao menos uma** deve estar ativa |
| **NÃO pode ter (NOT)** | Não | Flags que, se ativas, **excluem** o beneficiário desta regra composta |
| **Janela de Co-ocorrência (dias)** | ✅ | `0` = mesma guia; `N` = eventos podem ter até N dias de distância |
| **Exige Ordem Cronológica** | ✅ | Checkbox: se marcado, o evento Obrigatório deve ocorrer **antes** do Alternativo |
| **Sexo Alvo** | ✅ | `Ambos`, `M` ou `F` |
| **Idade Mín / Máx** | ✅ | Faixa etária para aplicação do protocolo |
| **Janela Retroativa (meses)** | ✅ | Período de busca dos eventos. Slider 0–48 meses |
| **Nome da Flag Composta** | ✅ | Ex: `FL_RASTREIO_RENAL` |
| **Contexto Técnico** | ✅ | Agrupador. Ex: `PREVENTIVA` |
| **Narrativa Clínica** | Não | Descrição em linguagem natural do protocolo |

---

## 7. Aba 2 — Gestão do Dicionário

**Arquivo:** `funcoes_gestao_dicionario.py`  
**Função principal:** `render_aba_dicionario(session)`

Esta aba permite visualizar, editar e excluir as regras simples existentes no dicionário.

### Fluxo Completo da Gestão do Dicionário

```mermaid
flowchart TD
    A([Aba 2 aberta]) --> B[SELECT * FROM TB_DICIONARIO_REGRAS\nORDER BY CATEGORIA]
    B --> C{Dicionário\nvazio?}
    C -->|Sim| INFO[ℹ️ Nenhuma inteligência\nmapeada no momento]
    C -->|Não| D[Exibe tabela editável\ncom st.data_editor]

    D --> E{Usuário editou\nalguma linha?}
    E -->|Clicou Salvar Alterações| F[Detecta linhas alteradas\ncomparando df_original vs df_editado]
    F --> G{Há mudanças?}
    G -->|Não| WARN[⚠️ Nenhuma alteração detectada]
    G -->|Sim| H[Para cada linha alterada:\nUPDATE TB_DICIONARIO_REGRAS\nSET campos = ?\nWHERE CATEGORIA = ?]
    H --> I[✅ N regra(s) atualizada(s)]
    I --> J[st.rerun — recarrega a tela]

    D --> K[Seção: Apagar Regras]
    K --> L[Selectbox com todas as\nCATEGORIAS do dicionário]
    L --> M{Usuário selecionou\numa regra?}
    M -->|Sim| N[⚠️ Exibe aviso de consequências]
    N --> O{Clicou em\nConfirmar Exclusão?}
    O -->|Sim| P[DELETE FROM TB_DICIONARIO_REGRAS\nWHERE CATEGORIA = ?]
    P --> Q[✅ / ❌ Feedback + st.rerun]
```

### Campos Editáveis no Dicionário

| Coluna | Editável | Observação |
|---|---|---|
| `CATEGORIA` | ❌ | Chave primária — bloqueada para edição |
| `TIPO_REGRA` | ❌ | Definido na criação |
| `PERIODICIDADE` | ❌ | Definido na criação |
| `LIMIAR_VOLUME` | ✅ | Apenas relevante para regras VOLUME |
| `CONTEXTO_TECNICO` | ✅ | Agrupador editável |
| `COLUNA_ALVO` | ✅ | Colunas de busca separadas por vírgula |
| `MES_INICIO` | ✅ | Início da janela retroativa |
| `MESES_RETROATIVOS` | ✅ | Fim da janela retroativa |
| `PADRAO_REGEX` | ✅ | Expressão regular de busca |
| `NARRATIVA_CLINICA` | ✅ | Texto clínico |
| `DESCRICAO` | ✅ | Registro interno |

> **Atenção:** Editar uma regra **não** reprocessa automaticamente a tabela DNA. Após editar, é necessário ir à **Aba 3 (Processamento Global)** para aplicar as mudanças.

> **Atenção:** Excluir uma regra **remove** ela do dicionário e ela **não será mais processada** nos próximos lotes. Porém, a coluna `FL_*` correspondente **permanece na tabela DNA** (o histórico é preservado).

---

## 8. Aba 3 — Processamento Global (Sala de Controle)

**Arquivo:** `funcoes_gestao_total_dna.py`  
**Funções:** `render_aba_gestao_total(session)`, `reprocessar_dna_motor_python(session, categoria_alvo)`, `reprocessar_dna_motor_composto(session, categoria_alvo)`

Esta aba é o **coração do sistema**. Aqui ocorre o reprocessamento completo da Matriz DNA, atualizando **todas as flags** para **todos os beneficiários**.

### Fluxo da Interface da Sala de Controle

```mermaid
flowchart TD
    A([Aba 3 aberta]) --> B[Exibe contagem:\nN regras simples\nM regras compostas ativas]
    B --> C[Exibe aviso crítico\n4 etapas da operação]
    C --> D{Usuário marcou\na caixa de confirmação?}
    D -->|Não| WAIT[⚠️ Botão desabilitado\n— aguardando confirmação]
    D -->|Sim| E[Botão habilitado:\nINICIAR ATUALIZAÇÃO GLOBAL]

    E --> F{Clicou no botão?}
    F -->|Sim| G[spinner: Fase 1 em andamento...]
    G --> H[reprocessar_dna_motor_python\ncategoria_alvo = None]
    H --> I{Fase 1\nconcluída?}
    I -->|Erro| ERR[❌ Erro Crítico — exibe detalhe]
    I -->|Sucesso| J[✅ Fase 1 concluída\nspinner: Fase 2 em andamento...]
    J --> K[reprocessar_dna_motor_composto\ncategoria_alvo = None]
    K --> L{Fase 2\nconcluída?}
    L -->|Erro| ERR
    L -->|Sucesso| M[✅ Fase 2 concluída\n🎉 st.toast de sucesso]

    F -->|Não| N[Seção: Auditoria de Colunas]
    N --> O[Lista todas as colunas\nFL_* ativas na TB_DNA]
```

### 8.1 Motor Fase 1 — Regras Simples

**Função:** `reprocessar_dna_motor_python(session, categoria_alvo=None)`

Esta função é o **Motor Principal** do DNA Engine. Opera em um único passe SQL (Single-Pass) sobre a base de dados, processando todas as regras simples em uma única query de UPDATE.

#### Algoritmo do Motor Fase 1

```mermaid
flowchart TD
    A([reprocessar_dna_motor_python chamado]) --> B{categoria_alvo\npassado?}
    B -->|Sim| C[SELECT * FROM DICIONARIO\nWHERE CATEGORIA = categoria_alvo]
    B -->|Não| D[SELECT * FROM DICIONARIO\ntodas as regras]
    C --> E
    D --> E[Busca DATA_ÂNCORA:\nMAX da DATA_ATENDIMENTO\nna FATOPRODUCAO]

    E --> F{Para cada regra\nno DataFrame}

    F --> G[Sanitiza e valida:\nNome da coluna → remove chars especiais\nRegex → escapa aspas simples\nColunas → normaliza maiúsculas]

    G --> H{Qual TIPO_REGRA?}

    H -->|VIGENCIA| I["MAX(CASE WHEN regex_match AND filtro_tempo THEN 1 ELSE 0 END)"]
    H -->|VOLUME| J["CASE WHEN COUNT(DISTINCT NUMERO_GUIA) >= limiar THEN 1 ELSE 0 END"]
    H -->|FREQUENCIA| K{Qual PERIODICIDADE?}

    K -->|MENSAL| K1["COUNT(DISTINCT TRUNC(DATA, MONTH)) >= 3"]
    K -->|TRIMESTRAL| K2["COUNT(DISTINCT TRUNC(DATA, QUARTER)) >= 3"]
    K -->|SEMESTRAL| K3["COUNT(DISTINCT semestre) >= 2"]
    K -->|ANUAL| K4["MAX(CASE WHEN regex AND filtro_tempo THEN 1 ELSE 0 END)"]

    I --> L
    J --> L
    K1 --> L
    K2 --> L
    K3 --> L
    K4 --> L

    L[Acumula em listas:\ncolunas_para_criar\ncases_sql\nupdates_sql]

    L --> F

    F --> M{Todas as regras\nprocessadas?}
    M -->|Não| F
    M -->|Sim| N[ALTER TABLE TB_DNA\nADD COLUMN IF NOT EXISTS\npara cada FL_*]
    N --> O[UPDATE TB_DNA\nSET todas as colunas FL_* = 0\nzera base]
    O --> P[Executa QUERY MESTRA:\nUPDATE TB_DNA\nFROM subquery com CASE WHEN\npara cada FL_*]
    P --> Q[✅ Retorna: N regras simples processadas]
    P --> R[❌ raise Exception com detalhe do erro]
```

#### Query Mestra do Motor Fase 1 (Estrutura Simplificada)

```sql
-- Estrutura da Query Single-Pass gerada pelo motor
UPDATE TB_DNA DNA
SET
    FL_REGRA_1 = DADOS_PROCESSADOS.FL_REGRA_1,
    FL_REGRA_2 = DADOS_PROCESSADOS.FL_REGRA_2,
    -- ... N colunas
FROM (
    WITH DADOS_PROCESSADOS AS (
        SELECT
            M.ID_PESSOA,
            -- Regra tipo VIGENCIA:
            MAX(CASE WHEN REGEXP_LIKE(F.SERVICO, 'ONCOLOG|QUIMIO', 'i')
                          AND DATEDIFF('month', F.DATA, data_ancora) BETWEEN 0 AND 3
                          AND (M.SEXO = 'Ambos' OR M.SEXO = 'M')
                          AND M.IDADE BETWEEN 0 AND 200
                     THEN 1 ELSE 0 END) AS FL_REGRA_1,
            -- Regra tipo VOLUME:
            CASE WHEN COUNT(DISTINCT CASE WHEN REGEXP_LIKE(F.CODIGO_CID, 'E11', 'i')
                                               AND DATEDIFF('month', ...) BETWEEN 0 AND 12
                                          THEN F.NUMERO_GUIA END) >= 5
                 THEN 1 ELSE 0 END AS FL_REGRA_2
        FROM FATOPRODUCAO F
        INNER JOIN USUARIOS M ON F.ID_USUARIO = M.ID_USUARIO
        GROUP BY M.ID_PESSOA
    )
    SELECT * FROM DADOS_PROCESSADOS
) DADOS_PROCESSADOS
WHERE CAST(DNA.ID_PESSOA AS VARCHAR) = CAST(DADOS_PROCESSADOS.ID_PESSOA AS VARCHAR)
```

### 8.2 Motor Fase 2 — Regras Compostas

**Função:** `reprocessar_dna_motor_composto(session, categoria_alvo=None)`

Este motor processa os **Protocolos Compostos**, que exigem cruzamento de múltiplos eventos por beneficiário com validação de janela temporal.

#### Algoritmo do Motor Fase 2

```mermaid
flowchart TD
    A([reprocessar_dna_motor_composto chamado]) --> B[SELECT * FROM DICIONARIO_COMPOSTO\nWHERE FL_ATIVO = 1]
    B --> C{DataFrame\nvazio?}
    C -->|Sim| RET[Retorna: nenhuma regra composta]
    C -->|Não| D[Carrega DICIONARIO_REGRAS\npara acessar os regex das flags simples]

    D --> E[Busca DATA_ÂNCORA]
    E --> F{Para cada regra\ncomposta}

    F --> G[Monta build_regex_clause\npara OBRIGATÓRIAS, ALTERNATIVAS e EXCLUSÃO]
    G --> H{janela_dias == 0?}
    H -->|Sim: Co-ocorrência\nna mesma guia| I[join_cond: B.NUMERO_GUIA = C.NUMERO_GUIA]
    H -->|Não| J{exige_ordem\ncronológica?}
    J -->|Sim| K["DATEDIFF(B→C) BETWEEN 0 AND janela_dias"]
    J -->|Não| L["ABS(DATEDIFF(B,C)) <= janela_dias"]
    I --> M
    K --> M
    L --> M

    M[Monta CTE por regra:\nCTE_FL_NOME AS\nSELECT DISTINCT ID_USUARIO\nFROM FATOPRODUCAO B\nJOIN USUARIOS M\nJOIN FATOPRODUCAO C\nWHERE obrig AND filtro_tempo AND NOT EXISTS exc]

    M --> F
    F --> N{Todas as regras\nprocessadas?}
    N -->|Não| F
    N -->|Sim| O[ALTER TABLE TB_DNA — ADD colunas]
    O --> P[UPDATE TB_DNA SET compostas = 0]
    P --> Q[Executa QUERY MESTRA COMPOSTA:\nWITH CTE_1, CTE_2, ...\nDADOS_PROCESSADOS AS SELECT + LEFT JOINs\nUPDATE TB_DNA FROM DADOS_PROCESSADOS]
    Q --> R[✅ N regras compostas processadas]
```

#### Lógica do Self-Join para Co-ocorrência

```mermaid
graph LR
    USR[USUARIOS M\nID_USUARIO] --> B[FATOPRODUCAO B\nEventos Obrigatórios]
    USR --> C[FATOPRODUCAO C\nEventos Alternativos]
    B -->|"janela_dias > 0 → ABS(DATEDIFF) ≤ janela"| J{JOIN de\nCo-ocorrência}
    B -->|"janela_dias = 0 → mesma NUMERO_GUIA"| J
    C --> J
    J --> EXC{NOT EXISTS\nEventos de Exclusão E?}
    EXC -->|Sem exclusão| RESULT[✅ ID_USUARIO elegível\npara flag composta]
    EXC -->|Com exclusão| REMOVE[❌ Removido da flag]
```

---

## 9. Aba 4 — Auditoria de Regras

**Arquivo:** `funcoes_auditoria_regras.py`  
**Função principal:** `render_aba_auditoria(session)`

Esta aba permite validar se um beneficiário que está com a flag `= 1` na TB_DNA possui, de fato, os registros na base de produção que justificam aquela flag. É a **prova real** da inteligência.

### Fluxo de Auditoria

```mermaid
flowchart TD
    A([Aba 4 aberta]) --> B[SELECT CATEGORIA + COLUNAS_ALVO\n+ PADRAO_REGEX FROM DICIONARIO]
    B --> C{Dicionário\nvazio?}
    C -->|Sim| INFO[ℹ️ Nenhuma regra para auditar]
    C -->|Não| D[Selectbox 1:\nEscolha a regra para auditar]

    D --> E[Determina nome da coluna:\nFL_CATEGORIA na TB_DNA]
    E --> F[SELECT ID_PESSOA FROM TB_DNA\nWHERE FL_CATEGORIA = 1 LIMIT 10]
    F --> G{Coluna existe\nna TB_DNA?}
    G -->|Não| WARN[⚠️ Coluna não criada ainda.\nExecute o Processamento Lote.]
    G -->|Sim| H{Há beneficiários\ncom flag = 1?}
    H -->|Não| WARN2[⚠️ Nenhum beneficiário encontrado\ncom esta flag ativa]
    H -->|Sim| I[Selectbox 2:\nEscolha o beneficiário]

    I --> J[Monta query dinâmica:\nSELECT colunas_fixas + colunas_extras\nFROM FATOPRODUCAO F\nINNER JOIN USUARIOS M\nWHERE ID_PESSOA = ?\nAND REGEXP_LIKE nas colunas_alvo]

    J --> K[Executa query com\nbind variables para segurança]
    K --> L{Registros\nencontrados?}
    L -->|Sim| OK[✅ Exibe N registros encontrados\nDataFrame com histórico do paciente]
    L -->|Não| ERR["❌ Inconsistência: flag = 1 mas\nnenhum registro bate na Silver!\n(sinal de dado desatualizado)"]
```

### Colunas Exibidas na Auditoria

A tabela de evidências exibe sempre as colunas fixas a seguir, mais eventuais colunas extras definidas na regra:

| Coluna | Fonte | Descrição |
|---|---|---|
| `ID_USUARIO` | FATOPRODUCAO | Identificador do usuário na transação |
| `USUARIO` | USUARIOS | Nome do beneficiário |
| `DATA_ATENDIMENTO` | FATOPRODUCAO | Data do atendimento formatada DD/MM/YYYY |
| `NUMERO_GUIA` | FATOPRODUCAO | Número da guia de autorização |
| `SERVICO` | FATOPRODUCAO | Serviço prestado |
| `SUBGR_SERVICO` | FATOPRODUCAO | Subgrupo do serviço |
| `GR_BENEFICIOS` | FATOPRODUCAO | Grupo de benefícios |
| `CODIGO_CID` | FATOPRODUCAO | CID-10 do atendimento |

---

## 10. Aba 5 — Visualizar Base

**Arquivo:** `funcoes_visualizacao_dados.py`  
**Função principal:** `render_aba_visualizacao(session)`

Esta aba oferece uma **prévia interativa** da tabela `TB_DNA` com controle de quantidade de registros.

### Fluxo de Visualização

```mermaid
flowchart TD
    A([Aba 5 aberta]) --> B[Slider: quantidade máxima\n10 a 1000 registros]
    B --> C[session.table TB_DNA .limit N .to_pandas]
    C --> D{Tabela\nexiste?}
    D -->|Não| WARN[⚠️ Tabela não criada ainda.\nProcesse a primeira regra.]
    D -->|Sim| E{DataFrame\nvazio?}
    E -->|Sim| INFO[ℹ️ Base vazia. Execute\no Processamento Global.]
    E -->|Não| F[Exibe N registros\nst.dataframe interativo\ncom busca, ordenação e download]
```

---

## 11. Referência Técnica das Funções

### `reprocessar_dna_motor_python(session, categoria_alvo=None)`

| Atributo | Valor |
|---|---|
| **Arquivo** | `funcoes_gestao_total_dna.py` |
| **Propósito** | Processar regras simples e atualizar a TB_DNA |
| **Parâmetro `categoria_alvo`** | Se `None` → processa todas as regras; se informado → processa apenas aquela categoria |
| **Retorno (sucesso)** | String: `"Sucesso! N regras simples processadas."` |
| **Retorno (erro)** | Levanta `Exception` com detalhe do erro |
| **Segurança** | Sanitização de nomes de colunas com `re.sub(r'[^A-Z0-9_]', '', ...)` para evitar SQL Injection |
| **Otimização** | Single-Pass: uma única query UPDATE processa todas as regras simultaneamente via CASE WHEN |

### `reprocessar_dna_motor_composto(session, categoria_alvo=None)`

| Atributo | Valor |
|---|---|
| **Arquivo** | `funcoes_gestao_total_dna.py` |
| **Propósito** | Processar protocolos compostos e atualizar a TB_DNA com flags de co-ocorrência |
| **Parâmetro `categoria_alvo`** | Se `None` → todas as compostas ativas; se informado → apenas aquela |
| **Retorno (sucesso)** | String: `"Sucesso! N regras compostas processadas."` |
| **Técnica SQL** | CTEs com Self-Join na FATOPRODUCAO para detectar co-ocorrência temporal |
| **Função auxiliar interna** | `build_regex_clause(lista_categorias_str, alias)` — converte lista de flags em cláusulas REGEXP_LIKE |

### `render_aba_execucao(session)`

| Atributo | Valor |
|---|---|
| **Arquivo** | `funcoes_execucao_regras.py` |
| **Propósito** | Renderiza o formulário de criação de regras (Aba 1) |
| **Dependência** | Importa `reprocessar_dna_motor_python` de `funcoes_gestao_total_dna` |
| **Segurança** | Usa bind variables (`?`) em todos os INSERTs para prevenir SQL Injection |

### `render_aba_dicionario(session)`

| Atributo | Valor |
|---|---|
| **Arquivo** | `funcoes_gestao_dicionario.py` |
| **Propósito** | Exibe, edita e exclui regras do dicionário (Aba 2) |
| **Mecanismo de detecção de mudanças** | `df_editado[df_dic.ne(df_editado).any(axis=1)]` — compara DataFrames Pandas |

### `render_aba_gestao_total(session)`

| Atributo | Valor |
|---|---|
| **Arquivo** | `funcoes_gestao_total_dna.py` |
| **Propósito** | Interface da Sala de Controle (Aba 3) com dupla confirmação de segurança |

### `render_aba_auditoria(session)`

| Atributo | Valor |
|---|---|
| **Arquivo** | `funcoes_auditoria_regras.py` |
| **Propósito** | Auditoria cruzada: DNA vs. base de produção (Aba 4) |
| **Segurança** | Bind variables em todos os parâmetros da query de auditoria |

### `render_aba_visualizacao(session)`

| Atributo | Valor |
|---|---|
| **Arquivo** | `funcoes_visualizacao_dados.py` |
| **Propósito** | Preview paginado da tabela TB_DNA (Aba 5) |

---

## 12. Glossário

| Termo | Definição |
|---|---|
| **DNA Engine** | Nome do sistema. Analogia à estrutura genética: cada flag é um "gene" que descreve a saúde/comportamento do beneficiário. |
| **Flag / `FL_*`** | Coluna booleana (0 ou 1) na tabela TB_DNA que indica se um critério foi satisfeito. |
| **Regra Simples** | Inteligência baseada em um único tipo de evento, detectado por regex em colunas da tabela fato. |
| **Regra Composta** | Protocolo que combina múltiplas regras simples com lógica AND/OR/NOT e co-ocorrência temporal. |
| **Janela de Vigência** | Intervalo de meses retroativos para busca de eventos. Ex: `-0 a -3 meses` = últimos 3 meses. |
| **Data Âncora** | A data mais recente registrada na tabela fato. Serve como referência para cálculo da janela retroativa. |
| **Co-ocorrência** | Dois ou mais eventos de saúde que ocorrem dentro de uma mesma janela de tempo (ou na mesma guia). |
| **Bio-Filtro** | Combinação de filtros de Sexo e Idade que restringe a aplicação de uma regra a um subgrupo específico. |
| **Single-Pass** | Técnica de otimização onde todas as regras são processadas em uma única query SQL, evitando múltiplas varreduras na tabela fato. |
| **Bind Variable** | Parâmetro `?` em queries SQL que previne SQL Injection, separando o código SQL dos dados. |
| **Camada Bronze** | Dados brutos de origem (FEDERACAO.BRONZE) — sem transformação. |
| **Camada Silver** | Dados curados e dicionários de regras (DB_GESTAO_SAUDE.SILVER). |
| **Camada Gold** | Produto analítico final — a Matriz DNA (DB_GESTAO_SAUDE.GOLD). |
| **Matriz DNA / TB_DNA** | A tabela Gold que agrega a visão analítica de cada beneficiário com todas as suas flags. |
| **CTE** | Common Table Expression — subquery nomeada usada para organizar queries SQL complexas. |
| **Regex / REGEXP_LIKE** | Expressão regular usada para busca de padrões textuais nas colunas da tabela fato. |
| **Snowpark** | API Python da Snowflake que permite executar operações diretamente no engine do Snowflake, sem mover dados. |

---

## 13. Guia do Operador (Usuário Final)

### Checklist de Operação Diária / Mensal

```mermaid
flowchart TD
    START([Início da operação]) --> A{É necessário\ncadastrar nova regra?}
    A -->|Sim| B[Ir para Aba 1 - Criar Nova Regra\nPreencher todos os campos\nClicar Salvar]
    B --> C[Verificar mensagem de sucesso]
    C --> D{A regra\nfoi processada?}
    D -->|Sim| E[Ir para Aba 4 - Auditoria\nSelecionar a nova regra\nVerificar se pacientes foram flagados corretamente]
    D -->|Não| ERR[Verificar mensagem de erro\nCorrigir campos e tentar novamente]

    A -->|Não| F{É necessário\natualizar toda a base?}
    F -->|Sim| G[Ir para Aba 3 - Processamento Global\nLer o aviso com atenção\nMarcar a caixa de confirmação\nClicar INICIAR ATUALIZAÇÃO]
    G --> H[Aguardar conclusão das Fases 1 e 2]
    H --> I[Ir para Aba 5 - Visualizar Base\nConferir se os dados estão corretos]

    F -->|Não| J{É necessário\neditar uma regra?}
    J -->|Sim| K[Ir para Aba 2 - Gestão do Dicionário\nEditar os campos desejados\nClicar Salvar Alterações\nDepois ir para Aba 3 e reprocessar]
    J -->|Não| DONE([Operação concluída ✅])

    E --> DONE
    I --> DONE
    K --> DONE
```

### Passo a Passo: Criando Sua Primeira Regra

1. **Acesse a Aba 1 — "Criar Nova Regra".**
2. Selecione o modo **"Regra Simples"**.
3. Defina a **Janela de Vigência**: para buscar eventos dos últimos 6 meses, coloque o slider em `(0, 6)`.
4. Escolha o **Sexo Alvo** e o **Tipo de Regra** (normalmente `VIGENCIA` para o início).
5. No formulário:
   - **Nome da Flag:** Ex: `DIABETICO_ATIVO` (o sistema cria automaticamente `FL_DIABETICO_ATIVO`)
   - **Colunas de Busca:** selecione `CODIGO_CID` e/ou `SERVICO`
   - **Padrão Regex:** Ex: `E10|E11|E12|E13|E14` (CIDs de diabetes)
   - **Contexto Técnico:** `DIABETES`
   - **Narrativa Clínica:** `Identifica beneficiários com diagnóstico ou procedimento relacionado a diabetes no período selecionado.`
6. Clique em **"Salvar Regra e Criar Coluna na DNA"**.
7. Aguarde a mensagem de sucesso.
8. Vá para a **Aba 4 — Auditoria** para verificar se os pacientes foram corretamente identificados.

### Boas Práticas

- **Nomeação de flags:** Use nomes claros e com contexto. Ex: `FL_ONCOLOGIA_ATIVA_3M` é melhor que `FL_ONCO`.
- **Regex:** Teste seus padrões antes de salvar. Use `|` para "OU". Ex: `QUIMIO|RADIOT|ONCOL`.
- **Janela de tempo:** Defina a janela conforme o critério clínico, não maior do que necessário.
- **Reprocessamento global:** Faça apenas quando necessário (mudança de muitas regras ou atualização mensal). É uma operação custosa.
- **Auditoria:** Sempre audite novas regras antes de usar os dados em produção.
- **Exclusão de regras:** Seja cauteloso. A coluna permanece na TB_DNA, mas a regra deixa de ser atualizada.

---

## 14. Guia do Desenvolvedor

### Como Adicionar uma Nova Aba

1. Crie um novo arquivo Python: `funcoes_nova_funcionalidade.py`
2. Implemente a função `render_aba_nova(session)` com a lógica da aba.
3. Em `streamlit_app.py`, adicione a importação e a aba:
   ```python
   from funcoes_nova_funcionalidade import render_aba_nova
   # ...
   t_nova = st.tabs([..., "Nova Funcionalidade"])
   with t_nova:
       render_aba_nova(session)
   ```

### Como Adicionar uma Nova Tabela Fonte

1. Declare as constantes em `config.py`:
   ```python
   TABELA_NOVA_FONTE = f"{SCHEMA_BRONZE_FEDERACAO}.TB_NOVA_FONTE"
   ```
2. Importe no módulo que precisar e use normalmente.

### Padrões de Segurança Obrigatórios

**Sempre use bind variables (`?`) para queries com entrada do usuário:**

```python
# ✅ CORRETO — seguro contra SQL Injection
session.sql("SELECT * FROM TABELA WHERE CATEGORIA = ?", params=[categoria]).collect()

# ❌ ERRADO — vulnerável a SQL Injection
session.sql(f"SELECT * FROM TABELA WHERE CATEGORIA = '{categoria}'").collect()
```

**Sempre sanitize nomes de colunas gerados dinamicamente:**

```python
# ✅ CORRETO — remove caracteres não alfanuméricos
nome_col = re.sub(r'[^A-Z0-9_]', '', nome_col.upper())

# ❌ ERRADO — permite injeção de SQL via nome da coluna
nome_col = user_input.upper()
```

### Como o Motor Single-Pass Funciona

A otimização central do DNA Engine é o conceito de **Single-Pass**: em vez de executar N queries de UPDATE (uma por regra), o motor:

1. Acumula todas as expressões `CASE WHEN` em uma lista Python.
2. Constrói **uma única query SQL** que avalia todos os casos simultaneamente em uma subquery CTE.
3. Executa um **único UPDATE** na TB_DNA com todos os resultados.

Isso reduz o tempo de processamento de `O(N × scan_da_tabela)` para `O(1 × scan_da_tabela)`, sendo N o número de regras.

### Estratégia de Atualização Incremental vs. Global

| Cenário | Estratégia |
|---|---|
| Nova regra criada (Aba 1) | `reprocessar_dna_motor_python(session, categoria_alvo="FL_NOVA")` — processa apenas a nova regra |
| Regra editada no dicionário | Ir para Aba 3 → Processamento Global (não há atalho para edição isolada) |
| Atualização mensal completa | Aba 3 → Processamento Global → Fase 1 + Fase 2 |

### Tratamento de Erros

- Todas as funções `render_aba_*` usam `try/except` e exibem erros amigáveis via `st.error()`.
- Os motores de processamento levantam `Exception` com mensagem detalhada para que a interface possa exibir o problema.
- A auditoria trata o caso de coluna inexistente na TB_DNA separadamente (flag ainda não processada).

### Dependências (`environment.yml`)

```yaml
dependencies:
  - python=3.11.*
  - snowflake-snowpark-python   # Integração Snowflake + Python
  - streamlit                   # Interface visual
  - pandas                      # Manipulação de DataFrames para comparação de dados
```

> Para adicionar novas bibliotecas (ex: plotly para gráficos), descomente ou adicione a linha em `environment.yml` e faça o deploy novamente.

---

*Documentação gerada para o projeto DNA Engine — Vanilson da Silva. Para dúvidas técnicas, consulte os arquivos-fonte no repositório.*
