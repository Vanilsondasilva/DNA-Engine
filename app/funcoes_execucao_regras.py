# Nome no Repositorio: funcoes_execucao_regras.py
# Objetivo: Criar regras com Janela Deslizante (VIGENCIA), Bio-Filtros e Multiplas Colunas.

import streamlit as st
import pandas as pd
from funcoes_gestao_total_dna import reprocessar_dna_motor_python

def render_aba_execucao(session):
    st.subheader("Configuracao de Regra de Inteligencia")

    # --- SELETOR DE MODO ---
    modo_criacao = st.radio(
        "Selecione o Nível de Complexidade da Regra:", 
        ["Regra Simples (Evento Único/Volume)", "Regra Composta (Cruzamento de Eventos)"], 
        horizontal=True
    )
    st.divider()
    
    # =========================================================================
    # MODO 1: REGRA SIMPLES
    # =========================================================================
    if modo_criacao == "Regra Simples (Evento Único/Volume)":
        # --- 1. CARGA DE COLUNAS (Apontando para a tabela otimizada YEAR2) ---
        try:
            colunas_base = session.table("DB_GESTAO_SAUDE.SILVER.TB_FATO_PRODUCAO_YEAR2").columns
        except:
            colunas_base = ["SERVICO", "GRUPO_ASSISTENCIAL", "SUBGR_SERVICO", "CODIGO_SERVICO", "CODIGO_CID"]

        # --- 2. CONFIGURACAO DE VIGENCIA (LINHA DESLIZANTE) ---
        st.write("### Janela de Vigencia")
        meses_range = st.slider(
            "Selecione o intervalo de meses retroativos (Inicio e Fim):",
            0, 48, (0, 3),
            help="Exemplo: (0, 3) olha os últimos 3 meses. (4, 24) olha do mês -4 até o -24."
        )
        mes_inicio, mes_fim = meses_range[0], meses_range[1]
        
        st.info(f"A inteligencia buscara dados entre -{mes_inicio} e -{mes_fim} meses atras, baseada na data mais recente da base Year2.")

        # --- 3. CONFIGURACAO BIO-PERFIL ---
        col_bio1, col_bio2 = st.columns([1, 1])
        
        with col_bio1:
            sexo_alvo = st.selectbox("Sexo Alvo", ["Ambos", "M", "F"])
            tipo_regra = st.selectbox("Tipo de Regra", ["VIGENCIA", "FREQUENCIA", "VOLUME"], key="sel_tipo_regra")
            periodicidade = None
            limiar_volume = 1
            if tipo_regra == "FREQUENCIA":
                periodicidade = st.selectbox("Periodicidade", ["MENSAL", "TRIMESTRAL", "SEMESTRAL", "ANUAL"], key="sel_peri")
            elif tipo_regra == "VOLUME":
                limiar_volume = st.number_input("Mínimo de Guias Distintas (≥)", min_value=1, value=5)

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

                contexto_tecnico = st.text_input(
                    "Contexto Técnico / Grupo", 
                    placeholder="Ex: ONCOLOGIA, CARDIOLOGIA, DIABETES",
                    help="Agrupador macro desta regra para facilitar a gestão."
                ).upper().strip()
                
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
            if not categoria or not regex or not narrativa or not alvos_selecionados or not contexto_tecnico:
                st.error("Erro: Preencha a Categoria, as Colunas, o Regex, a Narrativa Clínica e o Contexto Técnico.")
            else:
                try:
                    # 1. Insercao Segura no Dicionario usando Bind Variables (?)
                    query_insert = """
                        INSERT INTO DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS 
                        (CATEGORIA, PADRAO_REGEX, TIPO_REGRA, PERIODICIDADE, LIMIAR_VOLUME, COLUNA_ALVO, 
                         MES_INICIO, MESES_RETROATIVOS, SEXO_ALVO, IDADE_MIN, IDADE_MAX, 
                         DESCRICAO, NARRATIVA_CLINICA, CONTEXTO_TECNICO, DT_CRIACAO, 
                         DT_ATUALIZACAO) VALUES (
                         ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                         CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
                         )
                    """
                    
                    # Prepara as variáveis 
                    alvos_str = ", ".join(alvos_selecionados)
                    peri_val = str(periodicidade) if periodicidade else None

                    # Executa com segurança máxima
                    session.sql(query_insert, params=[
                        categoria, 
                        regex, 
                        tipo_regra, 
                        peri_val,
                        int(limiar_volume),
                        alvos_str,
                        float(mes_inicio), 
                        float(mes_fim), 
                        sexo_alvo, 
                        float(id_min), 
                        float(id_max), 
                        obs, 
                        narrativa, 
                        contexto_tecnico
                    ]).collect()
                    
                    # 2. Chamada do Motor Universal Python (Passando a categoria criada)
                    resultado = reprocessar_dna_motor_python(session, categoria_alvo=categoria)
                    
                    # 3. Verificação do retorno
                    if resultado and isinstance(resultado, str) and resultado.startswith("ERRO"):
                        st.error(f"Falha técnica na gravação: {resultado}")
                    else:
                        st.success(f"Regra {categoria} processada na janela de -{mes_inicio} a -{mes_fim} meses.")
                        # st.rerun() # Opcional: recarrega a tela limpando o formulário
                    
                except Exception as e:
                    st.error(f"Erro ao processar: {str(e)}")

    # =========================================================================
    # MODO 2: REGRA COMPOSTA
    # =========================================================================
    else:
        st.write("### Construção de Regra Composta (Protocolos)")
        
        # 1. Pega as categorias existentes no banco para preencher as opções
        try:
            df_flags = session.sql("SELECT CATEGORIA FROM DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS ORDER BY CATEGORIA").to_pandas()
            lista_flags = df_flags['CATEGORIA'].tolist() if not df_flags.empty else []
        except:
            lista_flags = []
            st.warning("Não foi possível carregar as flags do banco de dados.")

        with st.form("form_composta", clear_on_submit=True):
            
            # --- Seção 1: Cruzamento Lógico ---
            st.markdown("#### 1. Lógica do Protocolo")
            col_l1, col_l2, col_l3 = st.columns(3)
            with col_l1:
                req_obrig = st.multiselect("Obrigatório ter (AND)", lista_flags, help="Ex: Creatinina. Todas as regras selecionadas aqui DEVEM ocorrer.")
            with col_l2:
                req_alt = st.multiselect("Alternativo ter (OR)", lista_flags, help="Ex: Glicose ou Microalbuminúria. Pelo menos UMA deve ocorrer.")
            with col_l3:
                req_exc = st.multiselect("NÃO pode ter (NOT)", lista_flags, help="Ex: Diálise. Se o paciente tiver isso, ele é removido da flag final.")

            # --- Seção 2: Tempo e Espaço ---
            st.markdown("#### 2. Restrições de Tempo e Bio-Filtros")
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                janela_dias = st.number_input("Janela de Co-ocorrência (Dias)", min_value=0, value=30, help="0 = Tudo na mesma Guia. 30 = Exames podem ter até 30 dias de distância.")
                exige_ordem = st.checkbox("Exige Ordem Cronológica (Obrigatório primeiro, Alternativo depois)", value=False)
            
            with col_t2:
                sexo_alvo_comp = st.selectbox("Sexo Alvo (Protocolo)", ["Ambos", "M", "F"], key="sexo_comp")
                c_id1, c_id2 = st.columns(2)
                id_min_comp = c_id1.number_input("Idade Mín", min_value=0, value=0, key="id_min_comp")
                id_max_comp = c_id2.number_input("Idade Máx", min_value=0, value=120, key="id_max_comp")

            # --- Seção 3: Janela Retroativa Geral ---
            st.write("Janela de Análise Retroativa (Meses):")
            meses_range_comp = st.slider(
                "Selecione a janela:", 
                0, 48, (0, 12), 
                key="slider_comp", 
                help="Vai buscar as co-ocorrências dentro deste período."
            )
            mes_inicio_comp, mes_fim_comp = meses_range_comp[0], meses_range_comp[1]

            # --- Seção 4: Dados Finais ---
            st.markdown("#### 3. Dados da Flag Final")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                categoria_comp = st.text_input("Nome da Flag Composta (Ex: FL_RASTREIO_RENAL)").upper().strip()
                contexto_comp = st.text_input("Contexto Técnico / Grupo", placeholder="Ex: PREVENTIVA").upper().strip()
            with col_f2:
                narrativa_comp = st.text_area("Narrativa Clínica", placeholder="Paciente realizou rastreio de função renal completo...")

            executar_composta = st.form_submit_button("Gravar Protocolo Composto")

        # --- PROCESSAMENTO DO SAVE ---
        if executar_composta:
            if not categoria_comp or not contexto_comp:
                st.error("Preencha o Nome da Flag Composta e o Contexto Técnico.")
            elif len(req_obrig) == 0 and len(req_alt) == 0:
                st.error("Selecione pelo menos uma regra Obrigatória ou Alternativa.")
            else:
                try:
                    str_obrig = ",".join(req_obrig)
                    str_alt = ",".join(req_alt)
                    str_exc = ",".join(req_exc)
                    int_ordem = 1 if exige_ordem else 0

                    query_insert_comp = """
                        INSERT INTO DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_COMPOSTO 
                        (CATEGORIA_COMPOSTA, REGRAS_OBRIGATORIAS, REGRAS_ALTERNATIVAS, REGRAS_EXCLUSAO, 
                         JANELA_COOCORRENCIA_DIAS, EXIGE_ORDEM_CRONOLOGICA, MES_INICIO, MESES_RETROATIVOS, 
                         SEXO_ALVO, IDADE_MIN, IDADE_MAX, CONTEXTO_TECNICO, NARRATIVA_CLINICA, FL_ATIVO,
                         DT_CRIACAO, DT_ATUALIZACAO) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())
                    """

                    session.sql(query_insert_comp, params=[
                        categoria_comp, str_obrig, str_alt, str_exc, 
                        int(janela_dias), int_ordem, float(mes_inicio_comp), float(mes_fim_comp),
                        sexo_alvo_comp, float(id_min_comp), float(id_max_comp), 
                        contexto_comp, narrativa_comp
                    ]).collect()

                    st.success(f"Regra Composta '{categoria_comp}' salva com sucesso no dicionário!")
                    st.warning("Nota: A regra foi salva. O processamento das regras compostas ocorrerá no Motor de Segunda Camada (Próxima fase da implementação).")
                    
                except Exception as e:
                    st.error(f"Erro ao salvar regra composta: {str(e)}")
