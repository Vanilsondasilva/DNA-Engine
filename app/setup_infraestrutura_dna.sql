-- Nome no Repositorio: sp_motor_processamento_dna.sql
-- Objetivo: Motor unificado consolidando dados atraves da TB_DIM_USUARIO.

-- ==========================================
-- 1. LIMPEZA DE ASSINATURAS ANTERIORES (O "Teto" recuperado)
-- ==========================================
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR);
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, FLOAT);
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, FLOAT, VARCHAR, FLOAT, FLOAT);
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, FLOAT, FLOAT, VARCHAR, FLOAT, FLOAT);
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_REPROCESSAR_DNA_COMPLETO();

-- ==========================================
-- 2. PROCEDURE UNITÁRIA (O seu Motor Novo que funciona!)
-- ==========================================
CREATE OR REPLACE PROCEDURE DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(
    CATEGORIA_NOM VARCHAR, COLUNA_BUSCA VARCHAR, REGEX_VAL VARCHAR,
    TIPO_REGRA_VAL VARCHAR, PERIODICIDADE_VAL VARCHAR,
    MES_INICIO_VAL FLOAT, MES_FIM_VAL FLOAT,
    SEXO_VAL VARCHAR, IDADE_MIN_VAL FLOAT, IDADE_MAX_VAL FLOAT
)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'sp_gestao_dna_dinamico'
EXECUTE AS CALLER
AS
$$
import re

def sp_gestao_dna_dinamico(session, categoria_nom, coluna_busca, regex_val,
                            tipo_regra_val, periodicidade_val,
                            mes_inicio_val, mes_fim_val,
                            sexo_val, idade_min_val, idade_max_val):
    try:
        cat = str(categoria_nom).upper().strip()
        nome_col = cat if cat.startswith('FL_') else f'FL_{cat}'
        nome_col = re.sub(r'[^A-Z0-9_]', '', nome_col)

        regex = str(regex_val).replace("'", "''")
        tipo = str(tipo_regra_val).upper()
        peri_raw = str(periodicidade_val) if periodicidade_val and str(periodicidade_val) not in ('None', 'null', 'NULL') else None
        peri = peri_raw.upper() if peri_raw else None

        mes_ini = int(mes_inicio_val) if mes_inicio_val else 0
        mes_fim = int(mes_fim_val) if mes_fim_val else 0
        sexo = str(sexo_val) if sexo_val else 'Ambos'
        id_min = int(idade_min_val) if idade_min_val is not None else 0
        id_max = int(idade_max_val) if idade_max_val is not None else 200

        # A. GESTÃO NA TB_DNA
        session.sql(f"ALTER TABLE DB_GESTAO_SAUDE.GOLD.TB_DNA ADD COLUMN IF NOT EXISTS {nome_col} INTEGER DEFAULT 0").collect()
        session.sql(f"UPDATE DB_GESTAO_SAUDE.GOLD.TB_DNA SET {nome_col} = 0").collect()

        # B. DATA ÂNCORA
        data_ref_sql = 'DATA_ATENDIMENTO'
        result = session.sql(f"SELECT TO_VARCHAR(MAX({data_ref_sql}), 'YYYY-MM-DD') FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2").collect()
        if not result or result[0][0] is None:
            raise ValueError("A tabela de producao esta vazia. Nenhuma data ancora encontrada.")
        data_ancora_str = result[0][0]
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', data_ancora_str):
            raise ValueError(f"Formato inesperado para data ancora: '{data_ancora_str}'")

        # C. CLÁUSULA REGEX
        colunas_array = str(coluna_busca).split(',')
        condicoes_regex = [
            f"REGEXP_LIKE(F.{re.sub(r'[^A-Z0-9_]', '', col.strip().upper())}, '{regex}', 'i')"
            for col in colunas_array
            if col.strip()
        ]
        if not condicoes_regex:
            raise ValueError(f"Nenhuma coluna valida encontrada em COLUNA_BUSCA: '{coluna_busca}'")
        clausula_busca = '(' + ' OR '.join(condicoes_regex) + ')'

        # D. SUBQUERY (APONTANDO PARA A TB_DIM_USUARIO)
        subquery = ''
        if tipo == 'FREQUENCIA':
            limite_freq = mes_fim if mes_fim > 0 else 4
            if peri == 'MENSAL':
                subquery = f"SELECT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.TB_DIM_USUARIO M ON F.ID_USUARIO = M.ID_USUARIO WHERE {clausula_busca} AND DATEDIFF('month', F.{data_ref_sql}, '{data_ancora_str}'::DATE) <= {limite_freq} GROUP BY M.ID_PESSOA HAVING COUNT(DISTINCT TRUNC(F.{data_ref_sql}, 'MONTH')) >= 3"
            elif peri == 'TRIMESTRAL':
                subquery = f"SELECT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.TB_DIM_USUARIO M ON F.ID_USUARIO = M.ID_USUARIO WHERE {clausula_busca} AND DATEDIFF('quarter', F.{data_ref_sql}, '{data_ancora_str}'::DATE) <= {limite_freq} GROUP BY M.ID_PESSOA HAVING COUNT(DISTINCT TRUNC(F.{data_ref_sql}, 'QUARTER')) >= 3"
            elif peri == 'SEMESTRAL':
                subquery = f"SELECT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.TB_DIM_USUARIO M ON F.ID_USUARIO = M.ID_USUARIO WHERE {clausula_busca} AND DATEDIFF('year', F.{data_ref_sql}, '{data_ancora_str}'::DATE) <= 1 GROUP BY M.ID_PESSOA HAVING COUNT(DISTINCT CASE WHEN MONTH(F.{data_ref_sql}) <= 6 THEN 1 ELSE 2 END) >= 2"
            elif peri == 'ANUAL':
                subquery = f"SELECT DISTINCT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.TB_DIM_USUARIO M ON F.ID_USUARIO = M.ID_USUARIO WHERE {clausula_busca} AND DATEDIFF('month', F.{data_ref_sql}, '{data_ancora_str}'::DATE) <= 12"
            else:
                raise ValueError(f"Periodicidade invalida para FREQUENCIA: '{peri}'. Use MENSAL, TRIMESTRAL, SEMESTRAL ou ANUAL.")
        else:
            filtro_tempo = f"AND DATEDIFF('month', F.{data_ref_sql}, '{data_ancora_str}'::DATE) BETWEEN {mes_ini} AND {mes_fim}"
            subquery = f"SELECT DISTINCT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.TB_DIM_USUARIO M ON F.ID_USUARIO = M.ID_USUARIO WHERE {clausula_busca} {filtro_tempo}"

        # E. UPDATE FINAL (usa parâmetros para os valores de sexo e idade)
        sql_update = f"""
            UPDATE DB_GESTAO_SAUDE.GOLD.TB_DNA U
            SET {nome_col} = 1
            FROM ({subquery}) F
            WHERE CAST(U.ID_PESSOA AS VARCHAR) = CAST(F.ID_PESSOA AS VARCHAR)
              AND (U.SEXO = ? OR ? = 'Ambos')
              AND (U.IDADE BETWEEN ? AND ? OR U.IDADE IS NULL)
        """
        session.sql(sql_update, params=[sexo, sexo, id_min, id_max]).collect()

        return 'OK - Sucesso'
    except Exception as e:
        return f'ERRO: {str(e)}'
$$;

-- ==========================================
-- 3. PROCEDURE DE LOTE (O "Piso" recuperado)
-- ==========================================
CREATE OR REPLACE PROCEDURE DB_GESTAO_SAUDE.SILVER.SP_REPROCESSAR_DNA_COMPLETO()
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'sp_reprocessar_dna_completo'
EXECUTE AS CALLER
AS
$$
def sp_reprocessar_dna_completo(session):
    try:
        rows = session.sql("""
            SELECT CATEGORIA, COLUNA_ALVO, PADRAO_REGEX, TIPO_REGRA, PERIODICIDADE,
                   MES_INICIO, MESES_RETROATIVOS, SEXO_ALVO, IDADE_MIN, IDADE_MAX
            FROM DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS
        """).collect()

        contagem = 0
        for row in rows:
            cat   = row[0]
            col   = row[1] if row[1] is not None else ''
            reg   = row[2]
            tip   = row[3]
            per   = row[4] if row[4] is not None else 'NULL'
            m_ini = row[5] if row[5] is not None else 0
            m_fim = row[6] if row[6] is not None else 0
            sex   = row[7] if row[7] is not None else 'Ambos'
            i_min = row[8] if row[8] is not None else 0
            i_max = row[9] if row[9] is not None else 200

            session.sql(
                "CALL DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                params=[cat, col, reg, tip, per, m_ini, m_fim, sex, i_min, i_max]
            ).collect()
            contagem += 1

        return f'Sucesso: {contagem} regras reprocessadas.'
    except Exception as e:
        return f'Erro no lote: {str(e)}'
$$;
