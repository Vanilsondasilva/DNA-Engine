# Nome no Repositorio: funcoes_gestao_total_dna.py
# Objetivo: Sala de controle para reprocessamento completo da Matriz DNA.
# Segurança: Inclui travas para evitar execucoes acidentais e o novo motor otimizado em Snowpark.

import streamlit as st
import pandas as pd
import re

# ==========================================
# 1. MOTOR UNIVERSAL (Lote ou Regra Única)
# ==========================================
def reprocessar_dna_motor_python(session, categoria_alvo=None):
    """
    Motor Python/Snowpark otimizado e blindado. 
    Se categoria_alvo for None, reprocessa TUDO. Se tiver o nome, reprocessa só aquela regra.
    """
    try:
        # 1. Busca as regras (Todas ou apenas a que acabou de ser criada)
        if categoria_alvo:
            df_regras = session.sql("SELECT * FROM DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS WHERE CATEGORIA = ?", params=[categoria_alvo]).to_pandas()
        else:
            df_regras = session.sql("SELECT * FROM DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS").to_pandas()
        
        if df_regras.empty:
            return "Nenhuma regra encontrada para processar."

        # 2. Pega a Data Âncora
        data_ancora = session.sql("SELECT TO_VARCHAR(MAX(DATA_ATENDIMENTO), 'YYYY-MM-DD') FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2").collect()[0][0]

        # Listas para guardar nossas construções dinâmicas
        colunas_para_criar = []
        cases_sql = []
        updates_sql = []

        # 3. Loop no PYTHON (Rápido) para montar as regras
        for _, regra in df_regras.iterrows():
            
            # --- BLINDAGEM E SANITIZAÇÃO ---
            cat = str(regra['CATEGORIA']).upper().strip()
            nome_col = cat if cat.startswith('FL_') else f"FL_{cat}"
            # Remove qualquer coisa que não seja Letra, Número ou Underline:
            nome_col = re.sub(r'[^A-Z0-9_]', '', nome_col) 
            
            # Protege aspas simples no regex
            regex = str(regra['PADRAO_REGEX']).replace("'", "''") 
            
            # Limpa o nome das colunas também (evita SQL injection na coluna)
            colunas_brutas = str(regra['COLUNA_ALVO']).split(',')
            colunas_busca = [re.sub(r'[^A-Z0-9_]', '', col.strip().upper()) for col in colunas_brutas if col.strip()]
            # ----------------------------------------------------------------
            
            tipo = str(regra['TIPO_REGRA']).upper()
            peri = str(regra['PERIODICIDADE']).upper() if pd.notna(regra['PERIODICIDADE']) else 'NULL'
            
            mes_ini = int(regra['MES_INICIO']) if pd.notna(regra['MES_INICIO']) else 0
            mes_fim = int(regra['MESES_RETROATIVOS']) if pd.notna(regra['MESES_RETROATIVOS']) else 0
            sexo = str(regra['SEXO_ALVO'])
            id_min = int(regra['IDADE_MIN']) if pd.notna(regra['IDADE_MIN']) else 0
            id_max = int(regra['IDADE_MAX']) if pd.notna(regra['IDADE_MAX']) else 200

            # --- MONTANDO AS CONDIÇÕES BASE ---
            condicoes_regex = [f"REGEXP_LIKE(F.{col}, '{regex}', 'i')" for col in colunas_busca]
            clausula_busca = "(" + " OR ".join(condicoes_regex) + ")"
            filtro_perfil = f"(M.SEXO = '{sexo}' OR '{sexo}' = 'Ambos') AND (M.IDADE BETWEEN {id_min} AND {id_max} OR M.IDADE IS NULL)"
            
            if tipo == 'FREQUENCIA':
                limite_freq = mes_fim if mes_fim > 0 else 4
                if peri == 'MENSAL':
                    filtro_tempo = f"DATEDIFF('month', F.DATA_ATENDIMENTO, '{data_ancora}'::DATE) <= {limite_freq}"
                    condicao_agrupada = f"CASE WHEN COUNT(DISTINCT CASE WHEN {clausula_busca} AND {filtro_tempo} AND {filtro_perfil} THEN TRUNC(F.DATA_ATENDIMENTO, 'MONTH') END) >= 3 THEN 1 ELSE 0 END"
                elif peri == 'TRIMESTRAL':
                    filtro_tempo = f"DATEDIFF('quarter', F.DATA_ATENDIMENTO, '{data_ancora}'::DATE) <= {limite_freq}"
                    condicao_agrupada = f"CASE WHEN COUNT(DISTINCT CASE WHEN {clausula_busca} AND {filtro_tempo} AND {filtro_perfil} THEN TRUNC(F.DATA_ATENDIMENTO, 'QUARTER') END) >= 3 THEN 1 ELSE 0 END"
                elif peri == 'SEMESTRAL':
                    filtro_tempo = f"DATEDIFF('year', F.DATA_ATENDIMENTO, '{data_ancora}'::DATE) <= 1"
                    condicao_agrupada = f"CASE WHEN COUNT(DISTINCT CASE WHEN {clausula_busca} AND {filtro_tempo} AND {filtro_perfil} THEN CASE WHEN MONTH(F.DATA_ATENDIMENTO) <= 6 THEN 1 ELSE 2 END END) >= 2 THEN 1 ELSE 0 END"
                else: # ANUAL
                    filtro_tempo = f"DATEDIFF('month', F.DATA_ATENDIMENTO, '{data_ancora}'::DATE) <= 12"
                    condicao_agrupada = f"MAX(CASE WHEN {clausula_busca} AND {filtro_tempo} AND {filtro_perfil} THEN 1 ELSE 0 END)"
            else: # VIGENCIA
                filtro_tempo = f"DATEDIFF('month', F.DATA_ATENDIMENTO, '{data_ancora}'::DATE) BETWEEN {mes_ini} AND {mes_fim}"
                condicao_agrupada = f"MAX(CASE WHEN {clausula_busca} AND {filtro_tempo} AND {filtro_perfil} THEN 1 ELSE 0 END)"

            colunas_para_criar.append(f"ADD COLUMN IF NOT EXISTS {nome_col} INTEGER DEFAULT 0")
            cases_sql.append(f"{condicao_agrupada} AS {nome_col}")
            updates_sql.append(f"{nome_col} = DADOS_PROCESSADOS.{nome_col}")

        # 4. Executa a criação de colunas
        if colunas_para_criar:
            session.sql(f"ALTER TABLE DB_GESTAO_SAUDE.GOLD.TB_DNA {', '.join(colunas_para_criar)}").collect()

        # 5. Zera todas as flags na tabela DNA (preparação para o UPDATE)
        zerar_colunas = ", ".join([f"{col.split('=')[0].strip()} = 0" for col in updates_sql])
        session.sql(f"UPDATE DB_GESTAO_SAUDE.GOLD.TB_DNA SET {zerar_colunas}").collect()

        # 6. A QUERY MESTRA
        query_mestra = f"""
            WITH DADOS_PROCESSADOS AS (
                SELECT 
                    M.ID_PESSOA,
                    {', '.join(cases_sql)}
                FROM DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2 F 
                INNER JOIN DB_GESTAO_SAUDE.SILVER.TB_DIM_USUARIO M 
                    ON F.ID_USUARIO = M.ID_USUARIO
                GROUP BY M.ID_PESSOA
            )
            UPDATE DB_GESTAO_SAUDE.GOLD.TB_DNA DNA
            SET {', '.join(updates_sql)}
            FROM DADOS_PROCESSADOS
            WHERE CAST(DNA.ID_PESSOA AS VARCHAR) = CAST(DADOS_PROCESSADOS.ID_PESSOA AS VARCHAR)
        """

        # Executa o processamento pesado no banco
        session.sql(query_mestra).collect()

        return f"Sucesso! {len(df_regras)} regras processadas em uma única varredura."

    except Exception as e:
        raise Exception(str(e)) # Repassa o erro para o Streamlit tratar


# ==========================================
# 2. INTERFACE (SALA DE CONTROLE)
# ==========================================
def render_aba_gestao_total(session):
    st.markdown("### Sala de Controle - Processamento em Lote")
    
    # Painel de Status
    try:
        total_regras = session.sql("SELECT COUNT(*) FROM DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS").collect()[0][0]
        st.info(f"O Dicionário possui atualmente {total_regras} regras cadastradas.")
    except:
        st.error("Não foi possível acessar o dicionário de regras.")
        return

    # Avisos de Segurança
    st.error("""
        **ATENÇÃO: OPERAÇÃO CRÍTICA**
        Ao clicar no botão abaixo, o sistema irá:
        1. Percorrer TODAS as regras salvas no dicionário.
        2. Resetar os valores atuais na tabela GOLD.TB_DNA (zerar os flags).
        3. Recalcular cada regra para toda a base de beneficiários utilizando o Motor Single-Pass.
        
        Esta operação será processada de forma simultânea e unificada.
    """)

    # Trava de Segurança
    confirmacao = st.checkbox("Eu entendo que esta operação atualizará toda a base DNA e confirmo o reprocessamento.")

    if confirmacao:
        if st.button("🔄 INICIAR ATUALIZAÇÃO GLOBAL DO DNA", type="primary", use_container_width=True):
            with st.spinner("Executando motor unificado de lote... Acelerando o processamento."):
                try:
                    # Chamada do Motor em Python atualizado
                    resultado = reprocessar_dna_motor_python(session)
                    
                    # Feedback profissional: Sucesso
                    st.success(f"FINALIZADO: {resultado}")
                    st.toast("Base atualizada com sucesso!", icon="✅") 
                    
                except Exception as e:
                    st.error(f"Erro Crítico no Processamento: {str(e)}")
    else:
        st.warning("Marque a caixa de confirmação acima para habilitar o processamento global.")

    st.divider()
    st.subheader("Auditoria de Colunas")
    st.write("Verifique abaixo se as colunas criadas no banco coincidem com o seu dicionário.")
    
    try:
        cols_dna = session.table("DB_GESTAO_SAUDE.GOLD.TB_DNA").columns
        st.write(f"Colunas presentes na Gold: {', '.join([c for c in cols_dna if c.startswith('FL_')])}")
    except Exception as e:
        st.error("Erro ao carregar colunas da tabela de auditoria.")
