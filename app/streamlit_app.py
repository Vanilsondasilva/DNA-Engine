# Nome no Repositorio: app_principal_dna.py
# Objetivo: Orquestrador unificado das abas.

import streamlit as st
from snowflake.snowpark.context import get_active_session

# Importacao dos modulos organizados
from funcoes_execucao_regras import render_aba_execucao
from funcoes_gestao_dicionario import render_aba_dicionario
from funcoes_gestao_total_dna import render_aba_gestao_total
from funcoes_auditoria_regras import render_aba_auditoria # Modulo Novo
from funcoes_visualizacao_dados import render_aba_visualizacao

st.set_page_config(layout="wide", page_title="DNA Engine")
st.title("DNA Engine - Jornada do Paciente")

# Protecao de sessao mantida
try:
    session = get_active_session()
except Exception as e:
    st.error("Não foi possível conectar ao Snowflake. Verifique se o aplicativo está a rodar no ambiente correto.")
    st.stop()

# Navegacao Centralizada (Sem icones, focado no tecnico)
t_config, t_total, t_auditoria, t_dados = st.tabs([
    "Configurar Regras", 
    "Gestão Total DNA", 
    "Auditoria de Regras",
    "Visualizar Resultados"
])

with t_config:
    render_aba_execucao(session)
    st.markdown("---")
    render_aba_dicionario(session)

with t_total:
    render_aba_gestao_total(session)

with t_auditoria:
    # A nossa nova aba de prova real
    render_aba_auditoria(session)

with t_dados:
    render_aba_visualizacao(session)
