# Nome no Repositorio: funcoes_gestao_total_dna.py
# Objetivo: Sala de controle para reprocessamento completo da Matriz DNA.
# Segurança: Inclui travas para evitar execucoes acidentais e o novo motor otimizado em Snowpark.

import streamlit as st
import pandas as pd
import re
from config import (TABELA_FATO_PRODUCAO, TABELA_DIM_USUARIO, TABELA_DICIONARIO,
                    TABELA_DICIONARIO_COMPOSTO, TABELA_DNA,
                    COLUNA_DATA_ATENDIMENTO, COLUNA_ID_USUARIO,
                    COLUNA_ID_PESSOA, COLUNA_NUMERO_GUIA)

# ==========================================
# 1. MOTOR UNIVERSAL - FASE 1 (Regras Simples)
# ==========================================
def reprocessar_dna_motor_python(session, categoria_alvo=None):
    """
    Motor Python/Snowpark otimizado e blindado. 
    Se categoria_alvo for None, reprocessa TUDO. Se tiver o nome, reprocessa só aquela regra.
    """
    try:
        if categoria_alvo:
            df_regras = session.sql(f"SELECT * FROM {TABELA_DICIONARIO} WHERE CATEGORIA = ?", params=[categoria_alvo]).to_pandas()
        else:
            df_regras = session.sql(f"SELECT * FROM {TABELA_DICIONARIO}").to_pandas()
        
        if df_regras.empty:
            return "Nenhuma regra simples encontrada para processar."

        data_ancora = session.sql(f"SELECT TO_VARCHAR(MAX({COLUNA_DATA_ATENDIMENTO}), 'YYYY-MM-DD') FROM {TABELA_FATO_PRODUCAO}").collect()[0][0]
        if not data_ancora:
            raise Exception("A tabela de produção está vazia. Nenhuma data âncora encontrada para processar as regras.")

        colunas_para_criar = []
        cases_sql = []
        updates_sql = []

        for _, regra in df_regras.iterrows():
            
            # --- BLINDAGEM E SANITIZAÇÃO ---
            cat = str(regra['CATEGORIA']).upper().strip()
            nome_col = cat if cat.startswith('FL_') else f"FL_{cat}"
            nome_col = re.sub(r'[^A-Z0-9_]', '', nome_col) 
            regex = str(regra['PADRAO_REGEX']).replace("'", "''") 
            colunas_brutas = str(regra['COLUNA_ALVO']).split(',')
            colunas_busca = [re.sub(r'[^A-Z0-9_]', '', col.strip().upper()) for col in colunas_brutas if col.strip()]
            
            tipo = str(regra['TIPO_REGRA']).upper()
            peri = str(regra['PERIODICIDADE']).upper() if pd.notna(regra['PERIODICIDADE']) else 'NULL'
            mes_ini = int(regra['MES_INICIO']) if pd.notna(regra['MES_INICIO']) else 0
            mes_fim = int(regra['MESES_RETROATIVOS']) if pd.notna(regra['MESES_RETROATIVOS']) else 0
            limiar_volume = int(regra['LIMIAR_VOLUME']) if 'LIMIAR_VOLUME' in regra and pd.notna(regra['LIMIAR_VOLUME']) else 1
            sexo = str(regra['SEXO_ALVO'])
            id_min = int(regra['IDADE_MIN']) if pd.notna(regra['IDADE_MIN']) else 0
            id_max = int(regra['IDADE_MAX']) if pd.notna(regra['IDADE_MAX']) else 200

            # --- MONTANDO AS CONDIÇÕES BASE ---
            condicoes_regex = [f"REGEXP_LIKE(TO_VARCHAR(F.{col}), '{regex}', 'i')" for col in colunas_busca]
            clausula_busca = "(" + " OR ".join(condicoes_regex) + ")"
            filtro_perfil = f"(M.SEXO = '{sexo}' OR '{sexo}' = 'Ambos') AND (M.IDADE BETWEEN {id_min} AND {id_max} OR M.IDADE IS NULL)"
            
            if tipo == 'FREQUENCIA':
                limite_freq = mes_fim if mes_fim > 0 else 4
                if peri == 'MENSAL':
                    filtro_tempo = f"DATEDIFF('month', F.{COLUNA_DATA_ATENDIMENTO}, '{data_ancora}'::DATE) <= {limite_freq}"
                    condicao_agrupada = f"CASE WHEN COUNT(DISTINCT CASE WHEN {clausula_busca} AND {filtro_tempo} AND {filtro_perfil} THEN TRUNC(F.{COLUNA_DATA_ATENDIMENTO}, 'MONTH') END) >= 3 THEN 1 ELSE 0 END"
                elif peri == 'TRIMESTRAL':
                    filtro_tempo = f"DATEDIFF('quarter', F.{COLUNA_DATA_ATENDIMENTO}, '{data_ancora}'::DATE) <= {limite_freq}"
                    condicao_agrupada = f"CASE WHEN COUNT(DISTINCT CASE WHEN {clausula_busca} AND {filtro_tempo} AND {filtro_perfil} THEN TRUNC(F.{COLUNA_DATA_ATENDIMENTO}, 'QUARTER') END) >= 3 THEN 1 ELSE 0 END"
                elif peri == 'SEMESTRAL':
                    filtro_tempo = f"DATEDIFF('month', F.{COLUNA_DATA_ATENDIMENTO}, '{data_ancora}'::DATE) <= 12"
                    condicao_agrupada = f"CASE WHEN COUNT(DISTINCT CASE WHEN {clausula_busca} AND {filtro_tempo} AND {filtro_perfil} THEN TRUNC(DATEDIFF('month', F.{COLUNA_DATA_ATENDIMENTO}, '{data_ancora}'::DATE) / 6) END) >= 2 THEN 1 ELSE 0 END"
                else: # ANUAL
                    filtro_tempo = f"DATEDIFF('month', F.{COLUNA_DATA_ATENDIMENTO}, '{data_ancora}'::DATE) <= 12"
                    condicao_agrupada = f"MAX(CASE WHEN {clausula_busca} AND {filtro_tempo} AND {filtro_perfil} THEN 1 ELSE 0 END)"
            
            elif tipo == 'VOLUME': 
                filtro_tempo = f"DATEDIFF('month', F.{COLUNA_DATA_ATENDIMENTO}, '{data_ancora}'::DATE) BETWEEN {mes_ini} AND {mes_fim}"
                condicao_agrupada = f"CASE WHEN COUNT(DISTINCT CASE WHEN {clausula_busca} AND {filtro_tempo} AND {filtro_perfil} THEN F.{COLUNA_NUMERO_GUIA} END) >= {limiar_volume} THEN 1 ELSE 0 END"
            
            else: # VIGENCIA
                filtro_tempo = f"DATEDIFF('month', F.{COLUNA_DATA_ATENDIMENTO}, '{data_ancora}'::DATE) BETWEEN {mes_ini} AND {mes_fim}"
                condicao_agrupada = f"MAX(CASE WHEN {clausula_busca} AND {filtro_tempo} AND {filtro_perfil} THEN 1 ELSE 0 END)"

            colunas_para_criar.append(f"ADD COLUMN IF NOT EXISTS {nome_col} INTEGER DEFAULT 0")
            cases_sql.append(f"{condicao_agrupada} AS {nome_col}")
            updates_sql.append(f"{nome_col} = DADOS_PROCESSADOS.{nome_col}")

        if colunas_para_criar:
            session.sql(f"ALTER TABLE {TABELA_DNA} {', '.join(colunas_para_criar)}").collect()

        zerar_colunas = ", ".join([f"{col.split('=')[0].strip()} = 0" for col in updates_sql])
        session.sql(f"UPDATE {TABELA_DNA} SET {zerar_colunas}").collect()

        query_mestra = f"""
            WITH DADOS_PROCESSADOS AS (
                SELECT 
                    M.{COLUNA_ID_PESSOA},
                    {', '.join(cases_sql)}
                FROM {TABELA_FATO_PRODUCAO} F
                INNER JOIN {TABELA_DIM_USUARIO} M
                    ON F.{COLUNA_ID_USUARIO} = M.{COLUNA_ID_USUARIO}
                GROUP BY M.{COLUNA_ID_PESSOA}
            )
            UPDATE {TABELA_DNA} DNA
            SET {', '.join(updates_sql)}
            FROM DADOS_PROCESSADOS
            WHERE CAST(DNA.{COLUNA_ID_PESSOA} AS VARCHAR) = CAST(DADOS_PROCESSADOS.{COLUNA_ID_PESSOA} AS VARCHAR)
        """

        session.sql(query_mestra).collect()

        return f"Sucesso! {len(df_regras)} regras simples processadas."

    except Exception as e:
        raise Exception(str(e))


# ==========================================
# 2. MOTOR DE SEGUNDA CAMADA (Regras Compostas)
# ==========================================
def reprocessar_dna_motor_composto(session, categoria_alvo=None):
    """
    Motor Fase 2: Avalia a coexistência temporal de eventos. 
    Cruza as regras OBRIGATÓRIAS vs ALTERNATIVAS validando a janela em dias ou número da guia.
    """
    try:
        # Tenta buscar as regras compostas. Se a tabela não existir ou estiver vazia, ignora a Fase 2.
        try:
            if categoria_alvo:
                df_comp = session.sql(f"SELECT * FROM {TABELA_DICIONARIO_COMPOSTO} WHERE FL_ATIVO = 1 AND CATEGORIA_COMPOSTA = ?", params=[categoria_alvo]).to_pandas()
            else:
                df_comp = session.sql(f"SELECT * FROM {TABELA_DICIONARIO_COMPOSTO} WHERE FL_ATIVO = 1").to_pandas()
        except:
            return "Nenhuma regra composta configurada (Tabela vazia ou ausente)."

        if df_comp.empty:
            return "Nenhuma regra composta encontrada para processar."

        # Busca o dicionário de regras simples para "pegar emprestado" os Regex delas
        df_simp = session.sql(f"SELECT CATEGORIA, PADRAO_REGEX, COLUNA_ALVO FROM {TABELA_DICIONARIO}").to_pandas()
        dict_simples = {row['CATEGORIA']: row for _, row in df_simp.iterrows()}

        data_ancora = session.sql(f"SELECT TO_VARCHAR(MAX({COLUNA_DATA_ATENDIMENTO}), 'YYYY-MM-DD') FROM {TABELA_FATO_PRODUCAO}").collect()[0][0]
        if not data_ancora:
            raise Exception("A tabela de produção está vazia. Nenhuma data âncora encontrada para processar as regras compostas.")

        # Função auxiliar para gerar o bloco de REGEX de uma lista de flags (Ex: FL_CREATININA, FL_UREIA)
        def build_regex_clause(lista_categorias_str, alias):
            if not lista_categorias_str or pd.isna(lista_categorias_str): return "1=0"
            cats = [c.strip() for c in str(lista_categorias_str).split(',') if c.strip()]
            conds = []
            for cat in cats:
                if cat in dict_simples:
                    regex = str(dict_simples[cat]['PADRAO_REGEX']).replace("'", "''")
                    cols = str(dict_simples[cat]['COLUNA_ALVO']).split(',')
                    for c in cols:
                        c = re.sub(r'[^A-Z0-9_]', '', c.strip().upper())
                        conds.append(f"REGEXP_LIKE(TO_VARCHAR({alias}.{c}), '{regex}', 'i')")
            return "(" + " OR ".join(conds) + ")" if conds else "1=0"

        ctes = []
        cases_sql = []
        updates_sql = []
        colunas_para_criar = []
        nomes_compostas = []

        # Construindo as Queries (Self-Joins) para cada regra composta
        for _, regra in df_comp.iterrows():
            cat_comp = str(regra['CATEGORIA_COMPOSTA']).upper().strip()
            cat_comp = cat_comp if cat_comp.startswith('FL_') else f"FL_{cat_comp}"
            cat_comp = re.sub(r'[^A-Z0-9_]', '', cat_comp)
            nomes_compostas.append(cat_comp)

            # Lógica
            obrig_clause = build_regex_clause(regra['REGRAS_OBRIGATORIAS'], 'B')
            alt_clause = build_regex_clause(regra['REGRAS_ALTERNATIVAS'], 'C')
            exc_clause = build_regex_clause(regra['REGRAS_EXCLUSAO'], 'E')

            has_alt = bool(str(regra['REGRAS_ALTERNATIVAS']).strip())
            has_exc = bool(str(regra['REGRAS_EXCLUSAO']).strip())

            # Tempo e Perfil
            janela = int(regra['JANELA_COOCORRENCIA_DIAS'])
            ordem = int(regra['EXIGE_ORDEM_CRONOLOGICA'])
            mes_ini, mes_fim = float(regra['MES_INICIO']), float(regra['MESES_RETROATIVOS'])
            sexo, id_min, id_max = str(regra['SEXO_ALVO']), float(regra['IDADE_MIN']), float(regra['IDADE_MAX'])

            filtro_perfil = f"(M.SEXO = '{sexo}' OR '{sexo}' = 'Ambos') AND (M.IDADE BETWEEN {id_min} AND {id_max} OR M.IDADE IS NULL)"
            filtro_tempo_B = f"DATEDIFF('month', B.{COLUNA_DATA_ATENDIMENTO}, '{data_ancora}'::DATE) BETWEEN {mes_ini} AND {mes_fim}"
            filtro_tempo_C = f"DATEDIFF('month', C.{COLUNA_DATA_ATENDIMENTO}, '{data_ancora}'::DATE) BETWEEN {mes_ini} AND {mes_fim}"

            # Regra de Co-ocorrência (Mesma Guia OU Janela de Dias)
            if janela == 0:
                join_cond = f"B.{COLUNA_NUMERO_GUIA} = C.{COLUNA_NUMERO_GUIA}"
            else:
                if ordem == 1: # Obrigatório tem que ocorrer ANTES ou no mesmo dia do Alternativo
                    join_cond = f"(B.{COLUNA_NUMERO_GUIA} = C.{COLUNA_NUMERO_GUIA} OR (DATEDIFF('day', B.{COLUNA_DATA_ATENDIMENTO}, C.{COLUNA_DATA_ATENDIMENTO}) BETWEEN 0 AND {janela}))"
                else: # Podem ocorrer em qualquer ordem dentro da janela
                    join_cond = f"(B.{COLUNA_NUMERO_GUIA} = C.{COLUNA_NUMERO_GUIA} OR ABS(DATEDIFF('day', B.{COLUNA_DATA_ATENDIMENTO}, C.{COLUNA_DATA_ATENDIMENTO})) <= {janela})"

            # Montagem dinâmica do JOIN apenas se houver Regras Alternativas
            join_c = f"INNER JOIN {TABELA_FATO_PRODUCAO} C ON B.{COLUNA_ID_USUARIO} = C.{COLUNA_ID_USUARIO} AND {join_cond} AND {alt_clause} AND {filtro_tempo_C}" if has_alt else ""
            where_exc = f"AND NOT EXISTS (SELECT 1 FROM {TABELA_FATO_PRODUCAO} E WHERE E.{COLUNA_ID_USUARIO} = B.{COLUNA_ID_USUARIO} AND {exc_clause})" if has_exc else ""

            # CTE Específica da Regra
            cte_sql = f"""
            CTE_{cat_comp} AS (
                SELECT DISTINCT B.{COLUNA_ID_USUARIO}
                FROM {TABELA_FATO_PRODUCAO} B
                INNER JOIN {TABELA_DIM_USUARIO} M ON B.{COLUNA_ID_USUARIO} = M.{COLUNA_ID_USUARIO}
                {join_c}
                WHERE {obrig_clause} AND {filtro_tempo_B} AND {filtro_perfil}
                {where_exc}
            )
            """
            ctes.append(cte_sql)
            cases_sql.append(f"CASE WHEN CTE_{cat_comp}.{COLUNA_ID_USUARIO} IS NOT NULL THEN 1 ELSE 0 END AS {cat_comp}")
            updates_sql.append(f"{cat_comp} = DADOS_PROCESSADOS.{cat_comp}")
            colunas_para_criar.append(f"ADD COLUMN IF NOT EXISTS {cat_comp} INTEGER DEFAULT 0")

        if not ctes:
            return "Nenhuma regra composta válida para processar."

        # Cria as colunas no banco se for uma regra composta nova
        session.sql(f"ALTER TABLE {TABELA_DNA} {', '.join(colunas_para_criar)}").collect()

        # Zera as flags compostas atuais
        zerar_colunas = ", ".join([f"{col.split('=')[0].strip()} = 0" for col in updates_sql])
        session.sql(f"UPDATE {TABELA_DNA} SET {zerar_colunas}").collect()

        # Junta todas as CTEs num mega cruzamento otimizado
        with_clause = "WITH " + ",\n".join(ctes)
        joins_clause = "\n".join([f"LEFT JOIN CTE_{c} ON M.{COLUNA_ID_USUARIO} = CTE_{c}.{COLUNA_ID_USUARIO}" for c in nomes_compostas])

        query_mestra_composta = f"""
            {with_clause},
            DADOS_PROCESSADOS AS (
                SELECT 
                    M.{COLUNA_ID_PESSOA},
                    {', '.join(cases_sql)}
                FROM {TABELA_DIM_USUARIO} M
                {joins_clause}
            )
            UPDATE {TABELA_DNA} DNA
            SET {', '.join(updates_sql)}
            FROM DADOS_PROCESSADOS
            WHERE CAST(DNA.{COLUNA_ID_PESSOA} AS VARCHAR) = CAST(DADOS_PROCESSADOS.{COLUNA_ID_PESSOA} AS VARCHAR)
        """

        session.sql(query_mestra_composta).collect()

        return f"Sucesso! {len(df_comp)} regras compostas (Protocolos Avançados) processadas."

    except Exception as e:
        raise Exception(f"Erro na Fase 2 (Regras Compostas): {str(e)}")


# ==========================================
# 3. INTERFACE (SALA DE CONTROLE)
# ==========================================
def render_aba_gestao_total(session):
    st.markdown("### Sala de Controle - Processamento em Lote")
    
    try:
        total_regras = session.sql(f"SELECT COUNT(*) FROM {TABELA_DICIONARIO}").collect()[0][0]
        try:
            total_compostas = session.sql(f"SELECT COUNT(*) FROM {TABELA_DICIONARIO_COMPOSTO} WHERE FL_ATIVO = 1").collect()[0][0]
        except:
            total_compostas = 0
            
        st.info(f"O Dicionário possui atualmente **{total_regras}** regras simples e **{total_compostas}** regras compostas ativas.")
    except:
        st.error("Não foi possível acessar os dicionários de inteligência.")
        return

    st.error("""
        **ATENÇÃO: OPERAÇÃO CRÍTICA**
        Ao clicar no botão abaixo, o sistema irá:
        1. Percorrer TODAS as regras (Simples e Compostas).
        2. Resetar os valores atuais na tabela GOLD.TB_DNA.
        3. Executar a **Fase 1 (Motor Simples)** para base de dados.
        4. Executar a **Fase 2 (Motor de Co-ocorrência)** cruzando os eventos.
    """)

    confirmacao = st.checkbox("Eu entendo que esta operação atualizará toda a base DNA e confirmo o reprocessamento.")

    if confirmacao:
        if st.button("🔄 INICIAR ATUALIZAÇÃO GLOBAL DO DNA", type="primary", use_container_width=True):
            with st.spinner("Executando motor unificado... Fase 1 (Regras Simples) em andamento."):
                try:
                    # Roda Fase 1
                    res_fase1 = reprocessar_dna_motor_python(session)
                    st.success(f"Fase 1 concluída: {res_fase1}")
                    
                    with st.spinner("Executando cruzamento de dados... Fase 2 (Regras Compostas) em andamento."):
                        # Roda Fase 2
                        res_fase2 = reprocessar_dna_motor_composto(session)
                        st.success(f"Fase 2 concluída: {res_fase2}")
                    
                    st.toast("Base DNA atualizada com sucesso!", icon="✅") 
                    
                except Exception as e:
                    st.error(f"Erro Crítico no Processamento: {str(e)}")
    else:
        st.warning("Marque a caixa de confirmação acima para habilitar o processamento global.")

    st.divider()
    st.subheader("Auditoria de Colunas")
    st.write("Verifique abaixo se as colunas criadas coincidem com os seus dicionários.")
    
    try:
        cols_dna = session.table(TABELA_DNA).columns
        st.write(f"Colunas ativas na Gold: {', '.join([c for c in cols_dna if c.startswith('FL_')])}")
    except Exception as e:
        st.error("Erro ao carregar colunas da tabela de auditoria.")
