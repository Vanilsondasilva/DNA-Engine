# Nome no Repositorio: funcoes_execucao_regras.py
# Objetivo: Criar regras com Janela Deslizante (VIGENCIA), Bio-Filtros e Multiplas Colunas.

import streamlit as st

def render_aba_execucao(session):
    st.subheader("Configuracao de Regra de Inteligencia")
    
    # --- 1. CARGA DE COLUNAS (Apontando para a tabela otimizada YEAR2) ---
    try:
        colunas_base = session.table("DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2").columns
    except:
        colunas_base = ["SERVICO", "GRUPO_ASSISTENCIAL", "SUBGR_SERVICO", "CODIGO_SERVICO", "CODIGO_CID"]

    # --- 2. CONFIGURACAO DE VIGENCIA (LINHA DESLIZANTE) ---
    st.write("### Janela de Vigencia")
    meses_range = st.slider(
        "Selecione o intervalo de meses retroativos (Inicio e Fim):",
        0, 60, (0, 3),
        help="Exemplo: (0, 3) olha os últimos 3 meses. (4, 24) olha do mês -4 até o -24."
    )
    mes_inicio, mes_fim = meses_range[0], meses_range[1]
    
    st.info(f"A inteligencia buscara dados entre -{mes_inicio} e -{mes_fim} meses atras, baseada na data mais recente da base Year2.")

    # --- 3. CONFIGURACAO BIO-PERFIL ---
    col_bio1, col_bio2 = st.columns([1, 1])
    
    with col_bio1:
        sexo_alvo = st.selectbox("Sexo Alvo", ["Ambos", "M", "F"])
        tipo_regra = st.selectbox("Tipo de Regra", ["VIGENCIA", "FREQUENCIA"], key="sel_tipo_regra")
        periodicidade = None
        if tipo_regra == "FREQUENCIA":
            periodicidade = st.selectbox("Periodicidade", ["MENSAL", "TRIMESTRAL", "SEMESTRAL", "ANUAL"], key="sel_peri")

    with col_bio2:
        modo_idade = st.radio("Filtrar Idade por:", ["Sem Filtro", "Idade Especifica", "Faixa Etaria"], horizontal=True)
        
        id_min, id_max = 0, 200 # Padrao para 'Sem Filtro'
        
        if modo_idade == "Idade Especifica":
            id_esp = st.number_input("Digite a Idade", min_value=0, max_value=120, value=30)
            id_min, id_max = id_esp, id_esp
        elif modo_idade == "Faixa Etaria":
            ci1, ci2 = st.columns(2)
            id_min = ci1.number_input("Idade Minima", min_value=0, max_value=120, value=0)
            id_max = ci2.number_input("Idade Maxima", min_value=0, max_value=120, value=18)

    # --- 4. FORMULARIO DE DADOS TECNICOS ---
    with st.form("form_dados_regra", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            categoria = st.text_input("Nome da Flag (Ex: TRATAMENTO_ONCO_ATIVO)").upper().strip()
            
            alvos_selecionados = st.multiselect(
                "Colunas de Busca na Base", 
                colunas_base, 
                default=[] 
            )
            
            regex = st.text_input("Padrao Regex (Ex: ONCOLOG|QUIMIO|RADIOTERAP)")
            
        with c2:
            st.write("Narrativa para a Jornada do Paciente:")
            narrativa = st.text_area(
                "Texto Objetivo", 
                placeholder="Ex: Identifica utilizacao de oncologia no periodo selecionado.",
                help="Este texto sera usado para montar a historia clinica do individuo."
            )
            
            # Registro Interno Automatico (Concatenacao de todos os campos preenchidos)
            alvos_str = ", ".join(alvos_selecionados)
            registro_interno = (
                f"ID: {categoria} | TIPO: {tipo_regra} | JANELA: -{mes_inicio} a -{mes_fim}M | "
                f"COLUNAS: {alvos_str} | SEXO: {sexo_alvo} | "
                f"IDADE: {id_min} a {id_max} | REGEX: {regex}"
            )
            
            st.info(f"Registro Interno (Gerado): {registro_interno}")
            obs = registro_interno 

        executar = st.form_submit_button("Salvar Regra e Criar Coluna na DNA")

    # --- 5. EXECUCAO E SALVAMENTO ---
    if executar:
        if not categoria or not regex or not narrativa or not alvos_selecionados:
            st.error("Erro: Preencha a Categoria, as Colunas, o Regex e a Narrativa Clinica.")
        else:
            try:
                # Protecao contra aspas simples para seguranca SQL
                cat_segura = categoria.replace("'", "''")
                regex_segura = regex.replace("'", "''")
                narrativa_segura = narrativa.replace("'", "''")
                obs_segura = obs.replace("'", "''")
                alvos_seguro = alvos_str.replace("'", "''")
                
                # A. Insercao no Dicionario (Incluindo colunas da Janela Deslizante e Bio-Filtros)
                peri_sql = f"'{periodicidade}'" if periodicidade else "NULL"
                query_insert = f"""
                    INSERT INTO DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS 
                    (CATEGORIA, PADRAO_REGEX, TIPO_REGRA, PERIODICIDADE, COLUNA_ALVO, 
                     MES_INICIO, MESES_RETROATIVOS, SEXO_ALVO, IDADE_MIN, IDADE_MAX, DESCRICAO, NARRATIVA_CLINICA)
                    VALUES ('{cat_segura}', '{regex_segura}', '{tipo_regra}', {peri_sql}, '{alvos_seguro}', 
                            {mes_inicio}, {mes_fim}, '{sexo_alvo}', {id_min}, {id_max}, '{obs_segura}', '{narrativa_segura}')
                """
                session.sql(query_insert).collect()
                
                # B. Chamada do Motor (Procedure atualizada para 10 argumentos)
                resultado = session.call("DB_GESTAO_SAUDE.SILVER.SP_GESTAO_DNA_DINAMICO", 
                             categoria, alvos_str, regex, tipo_regra, str(periodicidade), 
                             float(mes_inicio), float(mes_fim), sexo_alvo, float(id_min), float(id_max))
                
                # NOVO: Verifica se o banco devolveu um erro na execução
                if resultado and isinstance(resultado, str) and resultado.startswith("ERRO"):
                    st.error(f"Falha técnica na gravação: {resultado}")
                else:
                    st.success(f"Regra {categoria} processada na janela de -{mes_inicio} a -{mes_fim} meses.")
                    st.rerun()
                
            except Exception as e:
                st.error(f"Erro ao processar: {str(e)}")
