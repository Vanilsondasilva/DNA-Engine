# Nome no Repositorio: funcoes_auditoria_regras.py
# Objetivo: Prova real. Validar se os pacientes flagados possuem o historico esperado (Via Camada SILVER).

import streamlit as st
import re
from config import TABELA_DICIONARIO, TABELA_DNA, TABELA_FATO_PRODUCAO, TABELA_DIM_USUARIO

def render_aba_auditoria(session):
    st.markdown("### 🔎 Auditoria de Regras")
    st.write("Selecione uma regra e um paciente para visualizar os eventos que ativaram a flag.")
    
    try:
        df_regras = session.sql("""
            SELECT CATEGORIA, COLUNA_ALVO, PADRAO_REGEX, TIPO_REGRA, PERIODICIDADE 
            FROM {TABELA_DICIONARIO} 
            ORDER BY CATEGORIA
        """).to_pandas()
        
        if df_regras.empty:
            st.info("Nenhuma regra encontrada no dicionário.")
            return
            
        c1, c2 = st.columns(2)
        
        with c1:
            regra_selecionada = st.selectbox("1. Selecione a Regra para auditar:", df_regras['CATEGORIA'].tolist())
        
        if regra_selecionada:
            detalhes = df_regras[df_regras['CATEGORIA'] == regra_selecionada].iloc[0]
            
            # Pega as variáveis base
            coluna_alvo_valor = str(detalhes['COLUNA_ALVO'])
            regex = str(detalhes['PADRAO_REGEX'])
            
            # Limpa o nome da coluna garantindo a formatação
            nome_col_dna = re.sub(r'[^A-Z0-9_]', '', f"FL_{regra_selecionada}")
            if nome_col_dna.startswith("FL_FL_"):
                nome_col_dna = nome_col_dna.replace("FL_FL_", "FL_")
                
            st.caption(f"**Lógica em teste:** Busca na(s) coluna(s) `{coluna_alvo_valor}` pelo padrão `{regex}`.")
            
            # 1. Busca os pacientes que tem a flag na tabela DNA
            query_pacientes = f"""
                SELECT ID_PESSOA 
                FROM {TABELA_DNA} 
                WHERE {nome_col_dna} = 1 
                LIMIT 10
            """
            
            try:
                df_pacientes = session.sql(query_pacientes).to_pandas()
            except Exception:
                with c2:
                    st.warning(f"A coluna {nome_col_dna} ainda não existe na tabela DNA. Execute o Processamento Lote primeiro.")
                return
            
            if df_pacientes.empty:
                with c2:
                    st.warning(f"Nenhum paciente encontrado com a flag {nome_col_dna} ativa na tabela DNA.")
            else:
                with c2:
                    paciente_alvo = st.selectbox("2. Selecione um Paciente (Amostra de até 100):", df_pacientes['ID_PESSOA'].tolist())
                
                if paciente_alvo:
                    st.markdown(f"#### Histórico do Paciente: `{paciente_alvo}`")
                    
                    # Prepara as múltiplas colunas para o SQL (adicionando o prefixo F. da tabela Fato)
                    colunas_array = [col.strip() for col in coluna_alvo_valor.split(",") if col.strip()]
                    
                    condicoes_regex = []
                    binds_regex = []
                    
                    for col in colunas_array:
                        condicoes_regex.append(f"REGEXP_LIKE(F.{col}, ?, 'i')")
                        binds_regex.append(regex)
                        
                    clausula_busca = "(" + " OR ".join(condicoes_regex) + ")"
                    
                    # --- SELECT ---
                    # 1. Definimos a ordem que NUNCA muda (já com os prefixos corretos)
                    ordem_fixa = [
                        "F.ID_USUARIO", 
                        "M.USUARIO",
                        "TO_VARCHAR(F.DATA_ATENDIMENTO, 'DD/MM/YYYY') AS DATA_ATENDIMENTO",
                        "F.NUMERO_GUIA", 
                        "F.SERVICO", 
                        "F.SUBGR_SERVICO", 
                        "F.GR_BENEFICIOS", 
                        "F.CODIGO_CID"
                    ]
                    
                    # 2. Iniciamos a lista com a ordem fixa
                    colunas_para_exibir = list(ordem_fixa)
                    
                    # 3. Adicionamos apenas o que for EXTRA na regra
                    # Comparamos apenas o nome da coluna (depois do ponto) para evitar duplicados
                    for col_regra in colunas_array:
                        col_limpa = col_regra.strip().upper()
                        # Se o nome da coluna não estiver na lista (comparando sem o prefixo F./M.)
                        if col_limpa not in [c.split(".")[-1].upper() for c in colunas_para_exibir]:
                            colunas_para_exibir.append(f"F.{col_regra.strip()}")

                    # Monta a string final do SELECT (AQUI ESTAVA O ERRO: removi o f"F.{c}")
                    cols_select_limpa = ", ".join(colunas_para_exibir)
                    
                    query_silver = f"""
                        SELECT 
                            {cols_select_limpa}
                        FROM {TABELA_FATO_PRODUCAO} F
                        INNER JOIN {TABELA_DIM_USUARIO} M
                            ON F.ID_USUARIO = M.ID_USUARIO
                        WHERE CAST(M.ID_PESSOA AS VARCHAR) = ?
                          AND {clausula_busca}
                        ORDER BY TRY_TO_DATE(LEFT(CAST(F.DATA_ATENDIMENTO AS VARCHAR), 10), 'DD/MM/YYYY') DESC NULLS LAST
                    """
                    
                    # Prepara os parâmetros (1º é o ID, os demais são o Regex repetido)
                    params_finais = [str(paciente_alvo)] + binds_regex
                    
                    with st.spinner("A cruzar dados com a base Silver (Year2)..."):
                        df_evidencias = session.sql(query_silver, params=params_finais).to_pandas()
                        
                        if not df_evidencias.empty:
                            st.success(f"Sucesso! Encontrados {len(df_evidencias)} registos que justificam esta flag.")
                            st.dataframe(
                                df_evidencias, 
                                use_container_width=True,
                                column_config={
                                    "ID_USUARIO": st.column_config.TextColumn("ID_USUARIO", width="small"),
                                    "USUARIO": st.column_config.TextColumn("USUARIO", width="medium"),
                                    "DATA_ATENDIMENTO": st.column_config.TextColumn("DATA_ATENDIMENTO", width="small"),
                                    "NUMERO_GUIA": st.column_config.TextColumn("NUMERO_GUIA", width="small"),
                                    "SERVICO": st.column_config.TextColumn("SERVICO", width="medium"),
                                    "SUBGR_SERVICO": st.column_config.TextColumn("SUBGR_SERVICO", width="small"),
                                    "GR_BENEFICIOS": st.column_config.TextColumn("GR_BENEFICIOS", width="small"),
                                    "CODIGO_CID": st.column_config.TextColumn("CODIGO_CID", width="small"),
                                }
                            )
                        else:
                            st.error("Inconsistência: Flag está como '1' no DNA, mas nenhum registo bate na base Silver.")
                            
    except Exception as e:
        st.error(f"Erro na auditoria. Detalhe técnico: {str(e)}")
