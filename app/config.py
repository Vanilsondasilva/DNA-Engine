# Nome no Repositorio: config.py
# Objetivo: Centralizar as fontes de dados para facilitar a troca de ambientes (Dev/Prod ou Novos Clientes)

# Mapeamento do Banco de Dados e Schemas
DATABASE = "DB_GESTAO_SAUDE"
SCHEMA_SILVER = f"{DATABASE}.SILVER"
SCHEMA_GOLD = f"{DATABASE}.GOLD"

# Tabelas Fonte (Mude aqui e o App inteiro se atualiza)
TABELA_FATO_PRODUCAO = f"{SCHEMA_SILVER}.TB_FATO_PRODUCAO_YEAR2"
TABELA_DIM_USUARIO   = f"{SCHEMA_SILVER}.TB_DIM_USUARIO"

# Tabelas do Motor DNA
TABELA_DICIONARIO          = f"{SCHEMA_SILVER}.TB_DICIONARIO_REGRAS"
TABELA_DICIONARIO_COMPOSTO = f"{SCHEMA_SILVER}.TB_DICIONARIO_COMPOSTO"
TABELA_DNA                 = f"{SCHEMA_GOLD}.TB_DNA"

# Nomes das colunas-chave da Tabela Fato (ajuste aqui se o nome for diferente no seu ambiente)
COLUNA_DATA_ATENDIMENTO = "DATA_ATENDIMENTO"
COLUNA_ID_USUARIO       = "ID_USUARIO"
COLUNA_ID_PESSOA        = "ID_PESSOA"
COLUNA_NUMERO_GUIA      = "NUMERO_GUIA"
