# Nome no Repositorio: funcoes_auditoria_regras.py
# Objetivo: Prova real. Validar se os pacientes flagados possuem o historico esperado.

import streamlit as st
import re

def render_aba_auditoria(session):
    st.markdown("### 🔎 Auditoria de Regras (A Prova Real)")
    st.write("Selecione uma regra e um paciente para visualizar os eventos brutos que ativaram a flag.")
    
    try:
        df_regras = session.sql("""
            SELECT CATEGORIA, COLUNA_ALVO, PADRAO_REGEX, TIPO_REGRA, PERIODICIDADE 
            FROM DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS 
            ORDER BY CATEGORIA
        """).to_pandas()
        
        if df_regras.empty:
            st.info("Nenhuma regra encontrada no dicionário.")
            return
            
        regra_selecionada = st.selectbox("1. Selecione a Regra para auditar:", df_regras['CATEGORIA'].tolist())
        
        if regra_selecionada:
            detalhes = df_regras[df_regras['CATEGORIA'] == regra_selecionada].iloc[0]
            
            # Pega a coluna que você selecionou no app
            coluna_alvo_valor = detalhes['COLUNA_ALVO'] 
            regex = detalhes['PADRAO_REGEX'].replace("'", "''") 
            nome_col_dna = re.sub(r'[^A-Z0-9_]', '', f"FL_{regra_selecionada}")
            
            st.caption(f"**Lógica em teste:** Busca na coluna `{coluna_alvo_valor}` pelo padrão `{regex}`.")
            
            query_pacientes = f"""
                SELECT ID_PESSOA 
                FROM DB_GESTAO_SAUDE.GOLD.TB_DNA 
                WHERE {nome_col_dna} = 1 
                LIMIT 100
            """
            
            try:
                df_pacientes = session.sql(query_pacientes).to_pandas()
            except Exception:
                st.warning(f"A coluna {nome_col_dna} ainda não existe na tabela DNA. Execute o Processamento Lote primeiro.")
                return
            
            if df_pacientes.empty:
                st.warning(f"Nenhum paciente encontrado com a flag {nome_col_dna} ativa na tabela DNA.")
            else:
                paciente_alvo = st.selectbox("2. Selecione um Paciente (Amostra de até 100):", df_pacientes['ID_PESSOA'].tolist())
                
                if paciente_alvo:
                    st.markdown(f"#### Histórico Bruto do Paciente: `{paciente_alvo}`")
                    
                    query_bronze = f"""
                        SELECT 
                            DATA_ATENDIMENTO_FATO_PRO, 
                            {coluna_alvo_valor}, 
                            DESCRICAO_CID, 
                            SERVICO
                        FROM FEDERACAO.BRONZE.FATOPRODUCAO
                        WHERE ID_PESSOA = '{paciente_alvo}'
                          AND REGEXP_LIKE({coluna_alvo_valor}, '{regex}', 'i')
                        ORDER BY TRY_TO_DATE(LEFT(DATA_ATENDIMENTO_FATO_PRO, 10), 'DD/MM/YYYY') DESC
                    """
                    
                    with st.spinner("A cruzar dados com a base Bronze..."):
                        df_evidencias = session.sql(query_bronze).to_pandas()
                        
                        if not df_evidencias.empty:
                            st.success(f"✔️ Sucesso! Encontrados {len(df_evidencias)} registos que justificam esta flag.")
                            st.dataframe(df_evidencias, use_container_width=True)
                        else:
                            st.error("⚠️ Inconsistência: Flag está como '1' no DNA, mas nenhum registo bate na Fato.")
                            
    except Exception as e:
        st.error(f"Erro na auditoria. Detalhe técnico: {str(e)}")
