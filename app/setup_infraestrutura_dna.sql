-- Nome no Repositorio: sp_motor_processamento_dna.sql
-- Objetivo: Motor unificado que suporta Regras Clínicas Temporais, Frequência e Múltiplas Colunas.

-- 1. LIMPEZA DE VERSÕES ANTERIORES (Garante que o Snowflake use a versão de 6 argumentos)
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR);
DROP PROCEDURE IF EXISTS DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, FLOAT);

-- 2. PROCEDURE UNITÁRIA (O Coração do Motor)
CREATE OR REPLACE PROCEDURE DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(
    CATEGORIA_NOM VARCHAR, COLUNA_BUSCA VARCHAR, REGEX_VAL VARCHAR, TIPO_REGRA_VAL VARCHAR, PERIODICIDADE_VAL VARCHAR, MESES_VAL FLOAT
)
RETURNS STRING LANGUAGE JAVASCRIPT EXECUTE AS CALLER AS
$$
    try {
        var cat = CATEGORIA_NOM.toUpperCase().trim();
        var nome_col = (cat.startsWith('FL_')) ? cat : "FL_" + cat;
        nome_col = nome_col.replace(/[^A-Z0-9_]/g, ''); 

        var regex = REGEX_VAL;
        var tipo = TIPO_REGRA_VAL.toUpperCase();
        var peri = (PERIODICIDADE_VAL && PERIODICIDADE_VAL !== 'None' && PERIODICIDADE_VAL !== 'null' && PERIODICIDADE_VAL !== 'NULL') ? PERIODICIDADE_VAL.toUpperCase() : null;
        var meses_filtro = parseInt(MESES_VAL) || 0;

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

        // --- B. LÓGICA DE MÚLTIPLAS COLUNAS (O "OU" Clínico) ---
        var colunas_array = COLUNA_BUSCA.split(',');
        var condicoes_regex = [];
        var binds_regex = [];
        for (var i = 0; i < colunas_array.length; i++) {
            var col_limpa = colunas_array[i].trim();
            if(col_limpa !== "") {
                condicoes_regex.push(`REGEXP_LIKE(${col_limpa}, ?, 'i')`);
                binds_regex.push(regex);
            }
        }
        var clausula_busca = "(" + condicoes_regex.join(" OR ") + ")";

        // --- C. DEFINIÇÃO DA SUBQUERY (FREQUÊNCIA vs REGRA CLÍNICA) ---
        var subquery = "";
        var data_ref = "TRY_TO_DATE(LEFT(DATA_ATENDIMENTO_FATO_PRO, 10), 'DD/MM/YYYY')";
        
        // Âncora de data: Pega a maior data da base para o cálculo retroativo
        var query_max_dt = "(SELECT MAX(" + data_ref + ") FROM FEDERACAO.BRONZE.FATOPRODUCAO)";

        if (tipo === 'FREQUENCIA') {
            // Mantendo EXATAMENTE a tua lógica de recorrência original
            if (peri === 'MENSAL') subquery = `SELECT ID_PESSOA, 1 FROM (SELECT ID_PESSOA, COUNT(DISTINCT TRUNC(${data_ref}, 'MONTH')) as QTD FROM FEDERACAO.BRONZE.FATOPRODUCAO WHERE ${clausula_busca} AND DATEDIFF('month', ${data_ref}, ${query_max_dt}) <= 4 GROUP BY 1) WHERE QTD >= 3`;
            else if (peri === 'TRIMESTRAL') subquery = `SELECT ID_PESSOA, 1 FROM (SELECT ID_PESSOA, COUNT(DISTINCT TRUNC(${data_ref}, 'QUARTER')) as QTD FROM FEDERACAO.BRONZE.FATOPRODUCAO WHERE ${clausula_busca} AND DATEDIFF('quarter', ${data_ref}, ${query_max_dt}) <= 4 GROUP BY 1) WHERE QTD >= 3`;
            else if (peri === 'SEMESTRAL') subquery = `SELECT ID_PESSOA, 1 FROM (SELECT ID_PESSOA, COUNT(DISTINCT CASE WHEN MONTH(${data_ref}) <= 6 THEN 1 ELSE 2 END) as QTD FROM FEDERACAO.BRONZE.FATOPRODUCAO WHERE ${clausula_busca} AND DATEDIFF('year', ${data_ref}, ${query_max_dt}) <= 1 GROUP BY 1) WHERE QTD >= 2`;
            else if (peri === 'ANUAL') subquery = `SELECT DISTINCT ID_PESSOA, 1 FROM FEDERACAO.BRONZE.FATOPRODUCAO WHERE ${clausula_busca} AND DATEDIFF('month', ${data_ref}, ${query_max_dt}) <= 12`;
        } else {
            // REGRA CLÍNICA TEMPORAL (Usa o campo meses_retroativos do App)
            var filtro_tempo = (meses_filtro > 0) ? `AND DATEDIFF('month', ${data_ref}, ${query_max_dt}) <= ${meses_filtro}` : "";
            subquery = `SELECT DISTINCT ID_PESSOA, 1 FROM FEDERACAO.BRONZE.FATOPRODUCAO WHERE ${clausula_busca} ${filtro_tempo}`;
        }

        // --- D. EXECUÇÃO DO UPDATE FINAL ---
        var sql_update = `UPDATE DB_GESTAO_SAUDE.GOLD.TB_DNA U SET ${nome_col} = 1 FROM (${subquery}) F WHERE U.ID_PESSOA = F.ID_PESSOA`;
        
        snowflake.createStatement({
            sqlText: sql_update,
            binds: binds_regex
        }).execute();

        return "OK";
    } catch (err) { return "ERRO: " + err.message; }
$$;

-- 3. PROCEDURE DE LOTE (Processamento Global)
CREATE OR REPLACE PROCEDURE DB_GESTAO_SAUDE.SILVER.SP_REPROCESSAR_DNA_COMPLETO()
RETURNS STRING LANGUAGE JAVASCRIPT EXECUTE AS CALLER AS
$$
    try {
        var regras = snowflake.createStatement({
            sqlText: `SELECT CATEGORIA, COLUNA_ALVO, PADRAO_REGEX, TIPO_REGRA, PERIODICIDADE, MESES_RETROATIVOS 
                      FROM DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS`
        }).execute();

        var contagem = 0;
        while (regras.next()) {
            var cat = regras.getColumnValue(1);
            var col = regras.getColumnValue(2);
            var reg = regras.getColumnValue(3);
            var tip = regras.getColumnValue(4);
            var per = regras.getColumnValue(5) || 'NULL';
            var mes = regras.getColumnValue(6) || 0;
            
            snowflake.createStatement({
                sqlText: `CALL DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO(?, ?, ?, ?, ?, ?)`,
                binds: [cat, col, reg, tip, per, mes]
            }).execute();
            contagem++;
        }
        return "Sucesso: " + contagem + " regras reprocessadas.";
    } catch (err) { return "Erro no lote: " + err.message; }
$$;
