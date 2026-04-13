# Nome no Repositorio: funcoes_gestao_dicionario.py
# Objetivo: Gestão completa do Dicionário (Edição de Regex, Colunas, Tempo, Narrativa e Exclusão).

import streamlit as st

def render_aba_dicionario(session):
    st.subheader("Gestão do Dicionário de Inteligência")
    
    # 1. BUSCA COMPLETA: Trazendo todas as colunas físicas do banco
    try:
        df_dic = session.sql("""
            SELECT 
                CATEGORIA, 
                TIPO_REGRA,
                COLUNA_ALVO, 
                MESES_RETROATIVOS, 
                PADRAO_REGEX, 
                NARRATIVA_CLINICA,
                DESCRICAO
            FROM DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS 
            ORDER BY CATEGORIA
        """).to_pandas()
    except Exception as e:
        st.error(f"Erro ao carregar dicionário: {str(e)}")
        return

    if df_dic.empty:
        st.info("Nenhuma inteligência mapeada no momento.")
        return

    # --- PARTE 1: EDIÇÃO ---
    st.write("### Editar Regras Existentes")
    st.caption("Ajuste os parâmetros abaixo. As alterações só serão gravadas ao clicar no botão 'Salvar Alterações'.")
    
    # EDITOR AVANÇADO: Configurado para cada tipo de dado
    df_editado = st.data_editor(
        df_dic, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "CATEGORIA": st.column_config.TextColumn("ID da Flag", disabled=True),
            "TIPO_REGRA": st.column_config.TextColumn("Tipo de Busca", disabled=True),
            "COLUNA_ALVO": st.column_config.TextColumn("Colunas (Base)", width="medium"),
            "MESES_RETROATIVOS": st.column_config.NumberColumn("Janela (Meses)", width="small", help="0 = Histórico Total"),
            "PADRAO_REGEX": st.column_config.TextColumn("Regex / Padrão", width="medium"),
            "NARRATIVA_CLINICA": st.column_config.TextColumn("Narrativa da Jornada", width="large"),
            "DESCRICAO": st.column_config.TextColumn("Registro Interno")
        }
    )
    
    col_save, _ = st.columns([1, 3])
    with col_save:
        if st.button("Salvar Alterações"):
            try:
                for index, row in df_editado.iterrows():
                    # Proteção contra aspas simples para não quebrar o SQL
                    reg_seguro = str(row['PADRAO_REGEX']).replace("'", "''")
                    nar_segura = str(row['NARRATIVA_CLINICA']).replace("'", "''")
                    obs_segura = str(row['DESCRICAO']).replace("'", "''")
                    col_segura = str(row['COLUNA_ALVO']).replace("'", "''")
                    
                    query_update = f"""
                        UPDATE DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS 
                        SET PADRAO_REGEX = '{reg_seguro}',
                            NARRATIVA_CLINICA = '{nar_segura}',
                            DESCRICAO = '{obs_segura}',
                            COLUNA_ALVO = '{col_segura}',
                            MESES_RETROATIVOS = {int(row['MESES_RETROATIVOS'])}
                        WHERE CATEGORIA = '{row['CATEGORIA']}'
                    """
                    session.sql(query_update).collect()
                
                st.success("Dicionário atualizado com sucesso!")
                st.balloons()
            except Exception as e:
                st.error(f"Erro ao atualizar: {str(e)}")

    st.divider()

    # --- PARTE 2: EXCLUSÃO ---
    st.write("### Apagar Regras")
    st.write("Selecione uma regra para remover definitivamente do dicionário de processamento.")
    
    # Selectbox para escolher a regra baseado no que existe no DF
    regra_para_deletar = st.selectbox(
        "Selecione a regra para excluir:", 
        [""] + df_dic['CATEGORIA'].tolist(),
        help="Cuidado: Esta ação remove a regra do dicionário e ela não será mais processada no lote."
    )
    
    if regra_para_deletar != "":
        st.warning(f"**Atenção:** Você está prestes a apagar a regra '{regra_para_deletar}'. Isso não removerá a coluna da tabela DNA (para preservar o histórico atual), mas a regra deixará de existir no dicionário e não será mais atualizada.")
        
        # Botão de confirmação específico para exclusão
        if st.button(f"Confirmar Exclusão de {regra_para_deletar}", type="secondary"):
            try:
                session.sql(f"DELETE FROM DB_GESTAO_SAUDE.SILVER.TB_DICIONARIO_REGRAS WHERE CATEGORIA = '{regra_para_deletar}'").collect()
                st.error(f"Regra '{regra_para_deletar}' removida com sucesso!")
                st.rerun() # Recarrega a página para atualizar a tabela
            except Exception as e:
                st.error(f"Erro ao excluir: {str(e)}")
