-- Nome no Repositorio: sp_motor_processamento_dna.sql
-- Objetivo: Motor unificado consolidando dados atraves da TB_DIM_USUARIO.

-- ==========================================
-- 1. LIMPEZA DE ASSINATURAS ANTERIORES (O "Teto" recuperado)
-- ==========================================
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR);
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, FLOAT);
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, FLOAT, VARCHAR, FLOAT, FLOAT);
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, FLOAT, FLOAT, VARCHAR, FLOAT, FLOAT);

-- ==========================================
-- 2. PROCEDURE UNITÁRIA (O seu Motor Novo que funciona!)
-- ==========================================
CREATE OR REPLACE PROCEDURE DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(
    CATEGORIA_NOM VARCHAR, COLUNA_BUSCA VARCHAR, REGEX_VAL VARCHAR, 
    TIPO_REGRA_VAL VARCHAR, PERIODICIDADE_VAL VARCHAR, 
    MES_INICIO_VAL FLOAT, MES_FIM_VAL FLOAT,
    SEXO_VAL VARCHAR, IDADE_MIN_VAL FLOAT, IDADE_MAX_VAL FLOAT
)
RETURNS STRING LANGUAGE JAVASCRIPT EXECUTE AS CALLER AS
$$
    try {
        var cat = CATEGORIA_NOM.toUpperCase().trim();
        var nome_col = (cat.startsWith('FL_')) ? cat : "FL_" + cat;
        nome_col = nome_col.replace(/[^A-Z0-9_]/g, ''); 

        var regex = REGEX_VAL.replace(/'/g, "''");
        var tipo = TIPO_REGRA_VAL.toUpperCase();
        var peri = (PERIODICIDADE_VAL && PERIODICIDADE_VAL !== 'None' && PERIODICIDADE_VAL !== 'null' && PERIODICIDADE_VAL !== 'NULL') ? PERIODICIDADE_VAL.toUpperCase() : null;
        
        var mes_ini = parseInt(MES_INICIO_VAL) || 0;
        var mes_fim = parseInt(MES_FIM_VAL) || 0;
        var sexo = SEXO_VAL || 'Ambos';
        var id_min = (IDADE_MIN_VAL !== null) ? parseInt(IDADE_MIN_VAL) : 0;
        var id_max = (IDADE_MAX_VAL !== null) ? parseInt(IDADE_MAX_VAL) : 200;

        // A. GESTÃO NA TB_DNA
        snowflake.createStatement({sqlText: `ALTER TABLE DB_GESTAO_SAUDE.GOLD.TB_DNA ADD COLUMN IF NOT EXISTS ${nome_col} INTEGER DEFAULT 0`}).execute();
        snowflake.createStatement({sqlText: `UPDATE DB_GESTAO_SAUDE.GOLD.TB_DNA SET ${nome_col} = 0`}).execute();

        // B. DATA ÂNCORA 
        var data_ref_sql = "DATA_ATENDIMENTO"; 
        var res_ancora = snowflake.createStatement({
            sqlText: `SELECT TO_VARCHAR(MAX(${data_ref_sql}), 'YYYY-MM-DD') FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2`
        }).execute();
        res_ancora.next();
        var data_ancora_str = res_ancora.getColumnValue(1);

        // C. CLÁUSULA REGEX
        var colunas_array = COLUNA_BUSCA.split(',');
        var condicoes_regex = [];
        for (var i = 0; i < colunas_array.length; i++) {
            var col_limpa = colunas_array[i].trim();
            if(col_limpa !== "") condicoes_regex.push(`REGEXP_LIKE(F.${col_limpa}, '${regex}', 'i')`);
        }
        var clausula_busca = "(" + condicoes_regex.join(" OR ") + ")";

        // D. SUBQUERY (APONTANDO PARA A TB_DIM_USUARIO)
        var subquery = "";
        if (tipo === 'FREQUENCIA') {
            var limite_freq = (mes_fim > 0) ? mes_fim : 4; 
            if (peri === 'MENSAL') {
                subquery = `SELECT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.TB_DIM_USUARIO M ON F.ID_USUARIO = M.ID_USUARIO WHERE ${clausula_busca} AND DATEDIFF('month', F.${data_ref_sql}, '${data_ancora_str}'::DATE) <= ${limite_freq} GROUP BY M.ID_PESSOA HAVING COUNT(DISTINCT TRUNC(F.${data_ref_sql}, 'MONTH')) >= 3`;
            } else if (peri === 'TRIMESTRAL') {
                subquery = `SELECT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.TB_DIM_USUARIO M ON F.ID_USUARIO = M.ID_USUARIO WHERE ${clausula_busca} AND DATEDIFF('quarter', F.${data_ref_sql}, '${data_ancora_str}'::DATE) <= ${limite_freq} GROUP BY M.ID_PESSOA HAVING COUNT(DISTINCT TRUNC(F.${data_ref_sql}, 'QUARTER')) >= 3`;
            } else if (peri === 'SEMESTRAL') {
                subquery = `SELECT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.TB_DIM_USUARIO M ON F.ID_USUARIO = M.ID_USUARIO WHERE ${clausula_busca} AND DATEDIFF('year', F.${data_ref_sql}, '${data_ancora_str}'::DATE) <= 1 GROUP BY M.ID_PESSOA HAVING COUNT(DISTINCT CASE WHEN MONTH(F.${data_ref_sql}) <= 6 THEN 1 ELSE 2 END) >= 2`;
            } else if (peri === 'ANUAL') {
                subquery = `SELECT DISTINCT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.TB_DIM_USUARIO M ON F.ID_USUARIO = M.ID_USUARIO WHERE ${clausula_busca} AND DATEDIFF('month', F.${data_ref_sql}, '${data_ancora_str}'::DATE) <= 12`;
            }
        } else {
            var filtro_tempo = `AND DATEDIFF('month', F.${data_ref_sql}, '${data_ancora_str}'::DATE) BETWEEN ${mes_ini} AND ${mes_fim}`;
            subquery = `SELECT DISTINCT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.TB_DIM_USUARIO M ON F.ID_USUARIO = M.ID_USUARIO WHERE ${clausula_busca} ${filtro_tempo}`;
        }

        // E. UPDATE FINAL
        var sql_update = `
            UPDATE DB_GESTAO_SAUDE.GOLD.TB_DNA U 
            SET ${nome_col} = 1 
            FROM (${subquery}) F 
            WHERE CAST(U.ID_PESSOA AS VARCHAR) = CAST(F.ID_PESSOA AS VARCHAR)
              AND (U.SEXO = ? OR ? = 'Ambos')
              AND (U.IDADE BETWEEN ? AND ? OR U.IDADE IS NULL)
        `;
        snowflake.createStatement({sqlText: sql_update, binds: [sexo, sexo, id_min, id_max]}).execute();

        return "OK - Sucesso";
    } catch (err) { return "ERRO: " + err.message; }
$$;

-- ==========================================
-- 3. PROCEDURE DE LOTE (O "Piso" recuperado)
-- ==========================================
CREATE OR REPLACE PROCEDURE DB_GESTAO_SAUDE.SILVER.SP_REPROCESSAR_DNA_COMPLETO()
RETURNS STRING LANGUAGE JAVASCRIPT EXECUTE AS CALLER AS
$$
    try {
        var regras = snowflake.createStatement({
            sqlText: `SELECT CATEGORIA, COLUNA_ALVO, PADRAO_REGEX, TIPO_REGRA, PERIODICIDADE, 
                             MES_INICIO, MESES_RETROATIVOS, SEXO_ALVO, IDADE_MIN, IDADE_MAX 
                      FROM DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS`
        }).execute();

        var contagem = 0;
        while (regras.next()) {
            var cat = regras.getColumnValue(1);
            var col = (regras.getColumnValue(2) == null) ? "" : regras.getColumnValue(2);
            var reg = regras.getColumnValue(3);
            var tip = regras.getColumnValue(4);
            var per = (regras.getColumnValue(5) == null) ? 'NULL' : regras.getColumnValue(5);
            var m_ini = regras.getColumnValue(6) || 0;
            var m_fim = regras.getColumnValue(7) || 0;
            var sex = regras.getColumnValue(8) || 'Ambos';
            var i_min = regras.getColumnValue(9) || 0;
            var i_max = (regras.getColumnValue(10) == null) ? 200 : regras.getColumnValue(10);
            
            snowflake.createStatement({
                sqlText: `CALL DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
                binds: [cat, col, reg, tip, per, m_ini, m_fim, sex, i_min, i_max]
            }).execute();
            contagem++;
        }
        return "Sucesso: " + contagem + " regras reprocessadas.";
    } catch (err) { return "Erro no lote: " + err.message; }
$$;
