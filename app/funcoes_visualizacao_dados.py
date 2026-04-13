# Nome no Repositorio: funcoes_visualizacao_dados.py
# Objetivo: Fornecer uma previa dos dados da tabela Gold.TB_DNA para auditoria.

import streamlit as st

def render_aba_visualizacao(session):
    st.subheader("Previa da Tabela GOLD.TB_DNA")
    
    limite = st.slider("Quantidade de registros:", 10, 500, 100)
    
    query = f"SELECT * FROM DB_GESTAO_SAUDE.GOLD.TB_DNA LIMIT {limite}"
    df_preview = session.sql(query).collect()
    
    st.dataframe(df_preview, use_container_width=True)
