# Nome no Repositorio: app_principal_dna.py
# Objetivo: Orquestrador unificado das abas.

import streamlit as st
from snowflake.snowpark.context import get_active_session

# Importacao dos modulos organizados
from funcoes_execucao_regras import render_aba_execucao
from funcoes_gestao_dicionario import render_aba_dicionario
from funcoes_gestao_total_dna import render_aba_gestao_total
from funcoes_visualizacao_dados import render_aba_visualizacao
from funcoes_auditoria_regras import render_aba_auditoria # <-- ATENÇÃO: Garanta que este arquivo existe!

st.set_page_config(layout="wide", page_title="DNA Engine")
st.title("DNA Engine - Jornada Inteligente")

# Protecao de sessao mantida
try:
    session = get_active_session()
except Exception as e:
    st.error("Não foi possível conectar ao Snowflake. Verifique se o aplicativo está a rodar no ambiente correto.")
    st.stop()

# Navegacao Centralizada: Agora com 5 abas para não sobrecarregar a tela
t_criar, t_dicionario, t_total, t_auditoria, t_dados = st.tabs([
    "Criar Nova Regra", 
    "Gestão do Dicionário", 
    "Processamento Global", 
    "Auditoria de Regras",
    "Visualizar Base"
])

with t_criar:
    render_aba_execucao(session)

with t_dicionario:
    render_aba_dicionario(session)

with t_total:
    render_aba_gestao_total(session)

with t_auditoria:
    render_aba_auditoria(session)

with t_dados:
    render_aba_visualizacao(session)
