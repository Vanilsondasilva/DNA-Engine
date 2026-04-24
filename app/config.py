# Nome no Repositorio: config.py
# Objetivo: Centralizar as fontes de dados para facilitar a troca de ambientes (Dev/Prod ou Novos Clientes)

# ==========================================
# Mapeamento dos Bancos de Dados e Schemas
# ==========================================

# 1. Banco Principal - Gestão de Saúde
DATABASE = "DB_GESTAO_SAUDE"
SCHEMA_SILVER = f"{DATABASE}.SILVER"
SCHEMA_GOLD = f"{DATABASE}.GOLD"

# 2. Banco Secundário - Federação (Adicionado para as tabelas fontes)
DATABASE_FEDERACAO = "FEDERACAO"
SCHEMA_BRONZE_FEDERACAO = f"{DATABASE_FEDERACAO}.BRONZE"


# ==========================================
# Tabelas Fonte
# ==========================================

# Atualizado: Agora apontam para a camada BRONZE do banco FEDERACAO
TABELA_FATO_PRODUCAO = f"{SCHEMA_BRONZE_FEDERACAO}.FATOPRODUCAO"
TABELA_DIM_USUARIO   = f"{SCHEMA_BRONZE_FEDERACAO}.USUARIOS"


# ==========================================
# Tabelas do Motor DNA
# ==========================================

# Mantido: Continuam usando a camada SILVER e GOLD do banco DB_GESTAO_SAUDE
TABELA_DICIONARIO          = f"{SCHEMA_SILVER}.TB_DICIONARIO_REGRAS"
TABELA_DICIONARIO_COMPOSTO = f"{SCHEMA_SILVER}.TB_DICIONARIO_COMPOSTO"
TABELA_DNA                 = f"{SCHEMA_GOLD}.TB_DNA"

# ==========================================
# Colunas Dinâmicas da Tabela Fato
# ==========================================
DATA_ATENDIMENTO = "TRY_TO_DATE(DATA_ATENDIMENTO_FATO_PRO, 'DD/MM/YYYY')"
