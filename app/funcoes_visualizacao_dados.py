# Nome no Repositorio: funcoes_visualizacao_dados.py
# Objetivo: Fornecer uma previa dos dados da tabela Gold.TB_DNA para auditoria.

import streamlit as st
import pandas as pd
from config import TABELA_DNA

def render_aba_visualizacao(session):
    st.subheader("Prévia da Tabela GOLD.TB_DNA")
    
    # Controle de paginação simples
    limite = st.slider("Quantidade máxima de registros para exibir:", min_value=10, max_value=1000, value=100, step=50)
    
    try:
        # Modo elegante e seguro do Snowpark (sem escrever texto SQL manual)
        # O .to_pandas() garante que a tabela terá recursos interativos (busca, ordenação, download)
        df_preview = session.table(TABELA_DNA).limit(limite).to_pandas()
        
        if df_preview.empty:
            st.info("A tabela DNA está vazia. Rode o processamento na Sala de Controle para gerar os dados.")
        else:
            st.write(f"Exibindo **{len(df_preview)}** registros capturados.")
            st.dataframe(df_preview, use_container_width=True)
            
    except Exception as e:
        st.warning("A tabela GOLD.TB_DNA ainda não foi criada ou está inacessível.")
        st.caption("Ela será criada automaticamente assim que você cadastrar e processar a primeira regra.")
