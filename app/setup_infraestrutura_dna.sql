-- Nome no Repositorio: sp_motor_processamento_dna.sql
-- Objetivo: Motor unificado consolidando dados por ID_PESSOA atraves da VIEW_DIM_USUARIO com normalizacao total.

-- 1. LIMPEZA DE ASSINATURAS ANTERIORES
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR);
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, FLOAT);
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, FLOAT, VARCHAR, FLOAT, FLOAT);
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, FLOAT, FLOAT, VARCHAR, FLOAT, FLOAT);

-- 2. PROCEDURE UNITÁRIA (10 Argumentos)
CREATE OR REPLACE PROCEDURE DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(
    CATEGORIA_NOM VARCHAR, 
    COLUNA_BUSCA VARCHAR, 
    REGEX_VAL VARCHAR, 
    TIPO_REGRA_VAL VARCHAR, 
    PERIODICIDADE_VAL VARCHAR, 
    MES_INICIO_VAL FLOAT, 
    MES_FIM_VAL FLOAT,
    SEXO_VAL VARCHAR, 
    IDADE_MIN_VAL FLOAT, 
    IDADE_MAX_VAL FLOAT
)
RETURNS STRING LANGUAGE JAVASCRIPT EXECUTE AS CALLER AS
$$
    try {
        // --- PREPARAÇÃO DE VARIÁVEIS ---
        var cat = CATEGORIA_NOM.toUpperCase().trim();
        var nome_col = (cat.startsWith('FL_')) ? cat : "FL_" + cat;
        nome_col = nome_col.replace(/[^A-Z0-9_]/g, ''); 

        // Escapa aspas simples no Regex para evitar quebra de SQL Injection
        var regex = REGEX_VAL.replace(/'/g, "''");
        
        var tipo = TIPO_REGRA_VAL.toUpperCase();
        var peri = (PERIODICIDADE_VAL && PERIODICIDADE_VAL !== 'None' && PERIODICIDADE_VAL !== 'null' && PERIODICIDADE_VAL !== 'NULL') ? PERIODICIDADE_VAL.toUpperCase() : null;
        
        var mes_ini = parseInt(MES_INICIO_VAL) || 0;
        var mes_fim = parseInt(MES_FIM_VAL) || 0;
        var sexo = SEXO_VAL || 'Ambos';
        var id_min = (IDADE_MIN_VAL !== null) ? parseInt(IDADE_MIN_VAL) : 0;
        var id_max = (IDADE_MAX_VAL !== null) ? parseInt(IDADE_MAX_VAL) : 200;

        // --- A. GESTÃO DE COLUNA NA TB_DNA ---
        var check = snowflake.createStatement({
            sqlText: `SELECT COUNT(*) FROM DB_GESTAO_SAUDE.INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'GOLD' AND TABLE_NAME = 'TB_DNA' AND COLUMN_NAME = ?`,
            binds: [nome_col]
        }).execute();
        check.next();
        if (check.getColumnValue(1) == 0) {
            snowflake.createStatement({sqlText: `ALTER TABLE DB_GESTAO_SAUDE.GOLD.TB_DNA ADD COLUMN ${nome_col} INTEGER DEFAULT 0`}).execute();
        }
        snowflake.createStatement({sqlText: `UPDATE DB_GESTAO_SAUDE.GOLD.TB_DNA SET ${nome_col} = 0`}).execute();

        // --- B. DATA ÂNCORA (Data mais recente na SILVER.TB_FATO_PRODUCAO_YEAR2) ---
        var data_ref_sql = "DATA_ATENDIMENTO"; 
        var res_ancora = snowflake.createStatement({
            sqlText: `SELECT MAX(${data_ref_sql}) FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 WHERE ${data_ref_sql} <= CURRENT_DATE()`
        }).execute();
        res_ancora.next();
        var data_ancora_obj = res_ancora.getColumnValue(1);
        var data_ancora_str = data_ancora_obj.toISOString().split('T')[0];

        // --- C. LÓGICA DE MÚLTIPLAS COLUNAS ---
        // CORREÇÃO 1: Injetamos o valor do regex direto na string ao invés de usar binds (?)
        var colunas_array = COLUNA_BUSCA.split(',');
        var condicoes_regex = [];
        for (var i = 0; i < colunas_array.length; i++) {
            var col_limpa = colunas_array[i].trim();
            if(col_limpa !== "") {
                condicoes_regex.push(`REGEXP_LIKE(F.${col_limpa}, '${regex}', 'i')`);
            }
        }
        var clausula_busca = "(" + condicoes_regex.join(" OR ") + ")";

        // --- D. DEFINIÇÃO DA SUBQUERY (VIGÊNCIA vs FREQUÊNCIA) COM MPI (ID_PESSOA) ---
        var subquery = "";
        var join_normalizado = "LTRIM(CAST(F.ID_USUARIO AS VARCHAR), '0') = LTRIM(CAST(M.ID_USUARIO AS VARCHAR), '0')";
        
        // CORREÇÃO 2: Removido o ", 1" dos selects. Selecionamos apenas M.ID_PESSOA.
        if (tipo === 'FREQUENCIA') {
            var limite_freq = (mes_fim > 0) ? mes_fim : 4; 
            if (peri === 'MENSAL') {
                subquery = `SELECT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.VIEW_DIM_USUARIO M ON ${join_normalizado} WHERE ${clausula_busca} AND DATEDIFF('month', F.${data_ref_sql}, '${data_ancora_str}'::DATE) <= ${limite_freq} GROUP BY M.ID_PESSOA HAVING COUNT(DISTINCT TRUNC(F.${data_ref_sql}, 'MONTH')) >= 3`;
            } else if (peri === 'TRIMESTRAL') {
                subquery = `SELECT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.VIEW_DIM_USUARIO M ON ${join_normalizado} WHERE ${clausula_busca} AND DATEDIFF('quarter', F.${data_ref_sql}, '${data_ancora_str}'::DATE) <= ${limite_freq} GROUP BY M.ID_PESSOA HAVING COUNT(DISTINCT TRUNC(F.${data_ref_sql}, 'QUARTER')) >= 3`;
            } else if (peri === 'SEMESTRAL') {
                subquery = `SELECT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.VIEW_DIM_USUARIO M ON ${join_normalizado} WHERE ${clausula_busca} AND DATEDIFF('year', F.${data_ref_sql}, '${data_ancora_str}'::DATE) <= 1 GROUP BY M.ID_PESSOA HAVING COUNT(DISTINCT CASE WHEN MONTH(F.${data_ref_sql}) <= 6 THEN 1 ELSE 2 END) >= 2`;
            } else if (peri === 'ANUAL') {
                subquery = `SELECT DISTINCT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.VIEW_DIM_USUARIO M ON ${join_normalizado} WHERE ${clausula_busca} AND DATEDIFF('month', F.${data_ref_sql}, '${data_ancora_str}'::DATE) <= 12`;
            }
        } else {
            var filtro_tempo = `AND DATEDIFF('month', F.${data_ref_sql}, '${data_ancora_str}'::DATE) BETWEEN ${mes_ini} AND ${mes_fim}`;
            subquery = `SELECT DISTINCT M.ID_PESSOA FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F INNER JOIN DB_GESTAO_SAUDE.SILVER.VIEW_DIM_USUARIO M ON ${join_normalizado} WHERE ${clausula_busca} AND F.${data_ref_sql} <= '${data_ancora_str}'::DATE ${filtro_tempo}`;
        }

        // --- E. UPDATE FINAL NA TB_DNA ---
        // CORREÇÃO 3: Os binds restantes agora batem certinho com as variáveis de perfil.
        var sql_update = `
            UPDATE DB_GESTAO_SAUDE.GOLD.TB_DNA U 
            SET ${nome_col} = 1 
            FROM (${subquery}) F 
            WHERE LTRIM(CAST(U.ID_PESSOA AS VARCHAR), '0') = LTRIM(CAST(F.ID_PESSOA AS VARCHAR), '0')
              AND (U.SEXO = ? OR ? = 'Ambos')
              AND (U.IDADE BETWEEN ? AND ?)
        `;
        
        snowflake.createStatement({
            sqlText: sql_update,
            binds: [sexo, sexo, id_min, id_max]
        }).execute();

        return "OK - Consolidado via VIEW_DIM_USUARIO. Ancora: " + data_ancora_str;
    } catch (err) { return "ERRO: " + err.message; }
$$;

-- 3. PROCEDURE DE LOTE (Reprocessamento Global)
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
