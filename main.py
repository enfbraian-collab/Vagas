import os
from sqlalchemy import TEXT
from conector_oracle import OracleConnector
from conector_Postgre import SupabaseConnector
import pandas as pd
import numpy as np
import gc
from functools import reduce
from query import CONTRATACAO
from otimizacao_memoria import otimizar_dataframe, reverter_categoricos_para_texto

##################################################################################################################### FUNCOES MODELAGEM

def extrair_dimensao_chave_natural(df_origem: pd.DataFrame, col_codigo: str, col_descricao: str, id_destino: str, desc_destino: str) -> pd.DataFrame:
    """
    Extrai, deduplica e padroniza uma dimensão que já possui um código/ID vindo do Oracle.
    """
    df_dimensao = df_origem[[col_codigo, col_descricao]].copy()
    df_dimensao = df_dimensao.drop_duplicates()
    df_dimensao = df_dimensao.dropna(subset=[col_codigo])
    df_dimensao = df_dimensao.rename(columns={
        col_codigo: id_destino,
        col_descricao: desc_destino
    })
    return df_dimensao


def extrair_dimensao_generica(df_origem: pd.DataFrame, mapeamento: dict, coluna_chave_destino: str) -> pd.DataFrame:
    """
    Extrai uma dimensão a partir de qualquer mapeamento {origem: destino},
    deduplicando e removendo nulos pela chave já renomeada.
    """
    df_dimensao = df_origem[list(mapeamento.keys())].copy()
    df_dimensao = df_dimensao.rename(columns=mapeamento)
    df_dimensao = df_dimensao.dropna(subset=[coluna_chave_destino])
    df_dimensao = df_dimensao.drop_duplicates(subset=[coluna_chave_destino])
    return df_dimensao


def salva_df_local(df: pd.DataFrame, nome_arquivo: str, caminho: str = r'C:\Users\WEMBLEY.MACEDO\Desktop\tabelas\\'):
    """
    Salva o DataFrame localmente, suportando Parquet, CSV e Excel dinamicamente.
    """
    caminho_completo = os.path.join(caminho, nome_arquivo)
    try:
        if nome_arquivo.endswith('.parquet'):
            df.to_parquet(caminho_completo, index=False)
        elif nome_arquivo.endswith('.csv'):
            df.to_csv(caminho_completo, index=False, sep=';', encoding='utf-8-sig')
        elif nome_arquivo.endswith('.xlsx'):
            df.to_excel(caminho_completo, index=False)
        else:
            print(f"❌ Formato de arquivo não suportado: {nome_arquivo}")
            return

        print(f"✅ DataFrame salvo localmente como {nome_arquivo}")

    except Exception as e:
        print(f"❌ Erro ao salvar DataFrame {nome_arquivo}: {e}")


def extrair_dim_sem_descricao(df_origem: pd.DataFrame, col_codigo: str, id_destino: str, desc_destino: str, prefixo_desc: str) -> pd.DataFrame:
    """
    Extrai e deduplica uma dimensão quando a origem só fornece o Código/ID.
    Gera automaticamente uma descrição genérica (Placeholder) para respeitar o DBML.
    """
    df_dimensao = df_origem[[col_codigo]].copy()
    df_dimensao = df_dimensao.drop_duplicates().dropna()
    df_dimensao = df_dimensao.rename(columns={col_codigo: id_destino})
    df_dimensao[desc_destino] = prefixo_desc + df_dimensao[id_destino].astype(str)
    return df_dimensao


def montar_fato(df_origem: pd.DataFrame, mapeamento: dict) -> pd.DataFrame:
    """
    Monta a Fato usando apenas um dicionário de mapeamento.
    """
    df_fato = df_origem[list(mapeamento.keys())].copy()
    df_fato = df_fato.rename(columns=mapeamento)

    for col in df_fato.columns:
        if 'DATA' in col.upper() or 'COMPETENCIA' in col.upper():
            df_fato[col] = pd.to_datetime(df_fato[col], errors='coerce')

    return df_fato


def identificar_duplicados(df: pd.DataFrame, coluna_chave: str) -> pd.DataFrame:
    """
    Identifica e retorna as linhas que possuem valores duplicados em uma coluna específica.
    """
    df_duplicados = df[df.duplicated(subset=[coluna_chave], keep=False)].sort_values(by=coluna_chave)

    qtd_linhas = len(df_duplicados)

    if qtd_linhas > 0:
        print(f"Atenção: Foram encontradas {qtd_linhas} linhas duplicadas na coluna '{coluna_chave}'.")
    else:
        print(f" Nenhum registro duplicado encontrado na coluna '{coluna_chave}'.")

    return df_duplicados


def contar_admissoes_mes(df: pd.DataFrame, ano: int, mes: int, col_data: str = 'data_admissao') -> int:
    """
    Conta quantos colaboradores únicos foram admitidos em um determinado mês/ano.
    """
    inicio = pd.Timestamp(year=ano, month=mes, day=1)
    fim = inicio + pd.offsets.MonthBegin(1)

    mask = (df[col_data] >= inicio) & (df[col_data] < fim)
    return df.loc[mask, 'sk_colaborador'].nunique()

def marcar_progresso(indice_atual: int, total: int, nome_tabela: str):
    """
    Exibe o progresso da carga (quantas tabelas já foram processadas / quantas faltam).
    """
    percentual = (indice_atual / total) * 100
    faltam = total - indice_atual
    print(f"📊 Progresso: {indice_atual}/{total} tabelas ({percentual:.1f}%) | Faltam {faltam} | Última: {nome_tabela}")

##################################################################################################################### FUNCOES PRINCIPAIS
#Conectar no Oracle, Lembra de associar com biblioteca para chamar as funções de dentro da classe.
CONECTAR = OracleConnector()
CONECTAR.conectar()
DF_CONTRATACAO = CONECTAR.executar_query(CONTRATACAO,chunksize=1000)
CONECTAR.fechar_conexao()

##########################################################################################
# ESTE CARAI VAI SEMPRE LEVAR O MESMO NOME DA CLASE QUANDO FOR ACIONADO
ENVIAR_POSTGRES = SupabaseConnector()
ENVIAR_POSTGRES._create_engine()
ENVIAR_POSTGRES.load_dataframe(DF_CONTRATACAO,"PLANILHA_VAGAS")
ENVIAR_POSTGRES.fechar_conexao()
print("vai corinthas")
################################################################################################