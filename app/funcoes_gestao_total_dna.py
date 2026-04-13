# Nome no Repositorio: funcoes_gestao_total_dna.py
# Objetivo: Sala de controle para reprocessamento completo da Matriz DNA.
# Segurança: Inclui travas para evitar execucoes acidentais.

import streamlit as st

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
        3. Recalcular cada regra para toda a base de beneficiários.
        
        Esta operação pode levar alguns minutos dependendo do volume de dados.
    """)

    # Trava de Segurança
    confirmacao = st.checkbox("Eu entendo que esta operação atualizará toda a base DNA e confirmo o reprocessamento.")

    if confirmacao:
        if st.button("🔄 INICIAR ATUALIZAÇÃO GLOBAL DO DNA", type="primary", use_container_width=True):
            with st.spinner("Executando motor de lote... Isso pode demorar."):
                try:
                    # Chama a Procedure de Lote
                    resultado = session.call("DB_GESTAO_SAUDE.SILVER.SP_REPROCESSAR_DNA_COMPLETO")
                    st.success(f"FINALIZADO: {resultado}")
                    st.balloons() # Feedback visual de sucesso
                except Exception as e:
                    st.error(f"Erro Crítico no Processamento: {str(e)}")
    else:
        st.warning("Marque a caixa de confirmação acima para habilitar o processamento global.")

    st.divider()
    st.subheader("Auditoria de Colunas")
    st.write("Verifique abaixo se as colunas criadas no banco coincidem com o seu dicionário.")
    
    cols_dna = session.table("DB_GESTAO_SAUDE.GOLD.TB_DNA").columns
    st.write(f"Colunas presentes na Gold: {', '.join([c for c in cols_dna if c.startswith('FL_')])}")
