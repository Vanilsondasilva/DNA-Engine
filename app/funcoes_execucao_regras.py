# Nome no Repositorio: funcoes_execucao_regras.py
# Objetivo: Criar regras com inteligência de tempo (meses) e busca em múltiplas colunas.

import streamlit as st

def render_aba_execucao(session):
    st.subheader("Nova Regra de Inteligência Clínica")
    
    # --- 1. INVESTIGAÇÃO DE DATAS (Para sua orientação) ---
    try:
        # Busca a menor e maior data para você não precisar adivinhar o período da base
        datas_base = session.sql("""
            SELECT 
                MIN(TRY_TO_DATE(LEFT(DATA_ATENDIMENTO_FATO_PRO, 10), 'DD/MM/YYYY')) as MIN_DT,
                MAX(TRY_TO_DATE(LEFT(DATA_ATENDIMENTO_FATO_PRO, 10), 'DD/MM/YYYY')) as MAX_DT
            FROM FEDERACAO.BRONZE.FATOPRODUCAO
        """).collect()[0]
        
        st.info(f"📅 **Período Detectado na Base:** De {datas_base['MIN_DT']} até {datas_base['MAX_DT']}")
    except:
        st.warning("Aviso: Não foi possível detectar as datas extremas da base Bronze.")

    # --- 2. CARGA DE COLUNAS ---
    try:
        colunas_base = session.table("FEDERACAO.BRONZE.FATOPRODUCAO").columns
    except:
        colunas_base = ["GRUPO_ESTATISTICO_G", "SERVICO", "DESCRICAO_CID"]

    # --- 3. CONFIGURAÇÃO DA REGRA ---
    col_tipo, col_meses = st.columns([1, 1])
    with col_tipo:
        tipo_regra = st.selectbox("Tipo de Regra", ["VIGÊNCIA", "FREQUENCIA"], key="sel_tipo_regra")
        periodicidade = None
        if tipo_regra == "FREQUENCIA":
            periodicidade = st.selectbox("Periodicidade", ["MENSAL", "TRIMESTRAL", "SEMESTRAL", "ANUAL"], key="sel_peri")

    with col_meses:
        # Aqui você define o período (Ex: 3 meses para a Oncologia)
        meses_retroativos = st.number_input(
            "Janela de Tempo (Meses Retroativos)", 
            min_value=0, max_value=60, value=0,
            help="O motor buscará dados desde a data máxima da base voltando este número de meses. 0 = Todo o histórico."
        )

    # --- 4. FORMULÁRIO DE DADOS ---
    with st.form("form_dados_regra", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            categoria = st.text_input("Nome da Flag (Ex: TRATAMENTO_ONCO_ATIVO)").upper().strip()
            
            # Mudança para MULTISELECT: Agora você escolhe SERVICO e GRUPO_ESTATISTICO_G juntos
            alvos_selecionados = st.multiselect(
                "Colunas de Busca na Base", 
                colunas_base, 
                default=["SERVICO"]
            )
            
            regex = st.text_input("Padrão Regex (Ex: ONCOLOG|QUIMIO|RADIOTERAP)")
            
        with c2:
            st.write("**Narrativa para a Jornada do Paciente:**")
            narrativa = st.text_area(
                "Texto Objetivo", 
                placeholder="Ex: Identifica utilização de oncologia nos últimos 3 meses.",
                help="Este texto será usado para montar a história clínica do indivíduo."
            )
            obs = st.text_input("Observação Interna")
        
        executar = st.form_submit_button("Salvar Regra e Gerar Inteligência")

    # --- 5. EXECUÇÃO E SALVAMENTO ---
    if executar:
        if not categoria or not regex or not narrativa or not alvos_selecionados:
            st.error("Erro: Preencha a Categoria, as Colunas, o Regex e a Narrativa.")
        else:
            try:
                # Prepara os dados para o SQL
                alvos_str = ", ".join(alvos_selecionados)
                peri_label = periodicidade if periodicidade else "UNICA"
                contexto_tecnico = f"{categoria} | {tipo_regra} | {meses_retroativos}M | {alvos_str} | {regex}"
                
                # Proteção contra aspas simples
                cat_segura = categoria.replace("'", "''")
                regex_segura = regex.replace("'", "''")
                narrativa_segura = narrativa.replace("'", "''")
                obs_segura = obs.replace("'", "''")
                alvos_seguro = alvos_str.replace("'", "''")
                contexto_seguro = contexto_tecnico.replace("'", "''")
                
                # A. Inserção no Dicionário (Com as colunas Alvo e Meses)
                peri_sql = f"'{periodicidade}'" if periodicidade else "NULL"
                query_insert = f"""
                    INSERT INTO DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS 
                    (CATEGORIA, PADRAO_REGEX, TIPO_REGRA, PERIODICIDADE, COLUNA_ALVO, MESES_RETROATIVOS, DESCRICAO, CONTEXTO_TECNICO, NARRATIVA_CLINICA)
                    VALUES ('{cat_segura}', '{regex_segura}', '{tipo_regra}', {peri_sql}, '{alvos_seguro}', {meses_retroativos}, '{obs_segura}', '{contexto_seguro}', '{narrativa_segura}')
                """
                session.sql(query_insert).collect()
                
                # B. Chamada do Motor (Procedure de 6 argumentos)
                # Passamos CATEGORIA, ALVOS, REGEX, TIPO, PERIODICIDADE e MESES
                session.call("DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO", 
                             categoria, alvos_str, regex, tipo_regra, str(periodicidade), float(meses_retroativos))
                
                st.success(f"Sucesso! Regra '{categoria}' processada nos últimos {meses_retroativos} meses.")
                st.rerun()
                
            except Exception as e:
                st.error(f"Erro ao processar: {str(e)}")
