# Nome no Repositorio: funcoes_gestao_dicionario.py
# Objetivo: Gestão completa do Dicionário (Edição de Regex, Colunas, Tempo, Narrativa e Exclusão).

import streamlit as st
import pandas as pd
from config import TABELA_DICIONARIO

def render_aba_dicionario(session):
    st.subheader("Gestão do Dicionário de Inteligência")
    
    # 1. BUSCA COMPLETA: Trazendo todas as colunas físicas do banco
    try:
        # <--- ADICIONAMOS MES_INICIO, LIMIAR_VOLUME e PERIODICIDADE AQUI
        df_dic = session.sql(f"""
            SELECT 
                CATEGORIA, 
                TIPO_REGRA,
                PERIODICIDADE,
                LIMIAR_VOLUME,
                CONTEXTO_TECNICO,
                COLUNA_ALVO, 
                MES_INICIO,
                MESES_RETROATIVOS, 
                PADRAO_REGEX, 
                NARRATIVA_CLINICA,
                DESCRICAO
            FROM {TABELA_DICIONARIO}
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
            "CATEGORIA": st.column_config.TextColumn("CATEGORIA", disabled=True),
            "TIPO_REGRA": st.column_config.TextColumn("TIPO REGRA", disabled=True),
            "PERIODICIDADE": st.column_config.TextColumn("PERIODICIDADE", disabled=True),
            "LIMIAR_VOLUME": st.column_config.NumberColumn("LIMIAR VOLUME", width="small", help="Apenas para regras de VOLUME"), # <--- NOVO
            "CONTEXTO_TECNICO": st.column_config.TextColumn("CONTEXTO TECNICO", width="medium"),
            "COLUNA_ALVO": st.column_config.TextColumn("CAMPO DE BUSCA (COLUNA_ALVO)", width="medium"),
            "MES_INICIO": st.column_config.NumberColumn("MES INICIO", width="small", help="0 = Mês atual"), # <--- NOVO
            "MESES_RETROATIVOS": st.column_config.NumberColumn("JANELA (MESES_RETROATIVOS)", width="small", help="0 = Histórico Total"),
            "PADRAO_REGEX": st.column_config.TextColumn("PADRÃO DE BUSCA", width="medium"),
            "NARRATIVA_CLINICA": st.column_config.TextColumn("NARRATIVA CLINICA", width="large"),
            "DESCRICAO": st.column_config.TextColumn("DESCRICAO")
        }
    )
    
    col_save, _ = st.columns([1, 3])
    with col_save:
        if st.button("Salvar Alterações", type="primary"):
            try:
                # Comparamos o original com o editado e pegamos apenas as linhas que mudaram
                mudancas = df_editado[df_dic.ne(df_editado).any(axis=1)]

                if mudancas.empty:
                    st.warning("Nenhuma alteração detectada.")
                else:
                    for index, row in mudancas.iterrows():
                        # O SQL só roda para as linhas dentro de 'mudancas'
                        # <--- ADICIONAMOS MES_INICIO e LIMIAR_VOLUME NO UPDATE
                        query_update = f"""
                            UPDATE {TABELA_DICIONARIO} 
                            SET PADRAO_REGEX = ?,
                                NARRATIVA_CLINICA = ?,
                                DESCRICAO = ?,
                                COLUNA_ALVO = ?,
                                MES_INICIO = ?,
                                MESES_RETROATIVOS = ?,
                                LIMIAR_VOLUME = ?,
                                CONTEXTO_TECNICO = ?,
                                DT_ATUALIZACAO = CURRENT_TIMESTAMP()
                            WHERE CATEGORIA = ?
                        """
                        
                        session.sql(query_update, params=[
                            str(row['PADRAO_REGEX']),
                            str(row['NARRATIVA_CLINICA']),
                            str(row['DESCRICAO']),
                            str(row['COLUNA_ALVO']),
                            float(row['MES_INICIO']),          # <--- NOVO PARÂMETRO
                            int(row['MESES_RETROATIVOS']),
                            int(row['LIMIAR_VOLUME']),         # <--- NOVO PARÂMETRO
                            str(row['CONTEXTO_TECNICO']) if pd.notna(row['CONTEXTO_TECNICO']) else "",
                            str(row['CATEGORIA'])
                        ]).collect()
                    
                    st.success(f"Sucesso! {len(mudancas)} regra(s) atualizada(s).")
                    st.rerun() # Recarrega para o original virar o novo 'editado'
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
                # 1. Trocamos o f-string por uma query com parâmetro (?)
                query_delete = f"DELETE FROM {TABELA_DICIONARIO} WHERE CATEGORIA = ?"
                
                # 2. Executamos passando a variável de forma segura na lista params
                session.sql(query_delete, params=[regra_para_deletar]).collect()
                
                st.error(f"Regra '{regra_para_deletar}' removida com sucesso!")
                st.rerun() # Recarrega a página para atualizar a tabela
            except Exception as e:
                st.error(f"Erro ao excluir: {str(e)}")
