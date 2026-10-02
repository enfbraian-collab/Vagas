import pandas as pd


def _memoria_mb(df: pd.DataFrame) -> float:
    """Memória real ocupada pelo DataFrame, em MB (deep=True considera o conteúdo de strings/objects)."""
    return df.memory_usage(deep=True).sum() / (1024 ** 2)


def downcast_numericos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reduz todas as colunas int/float para o menor subtipo capaz de
    representar os valores presentes (ex: int64 -> int8/int16/int32
    quando os valores permitem). Não depende do nome da coluna:
    varre os dtypes do próprio df.
    """
    colunas_int = df.select_dtypes(include=['int64', 'int32', 'int16']).columns
    for col in colunas_int:
        df[col] = pd.to_numeric(df[col], downcast='integer')

    colunas_float = df.select_dtypes(include=['float64', 'float32']).columns
    for col in colunas_float:
        df[col] = pd.to_numeric(df[col], downcast='float')

    return df


def downcast_categoricos(df: pd.DataFrame, limite_cardinalidade: float = 0.5) -> pd.DataFrame:
    """
    Converte colunas de texto (object) em 'category' quando a proporção
    de valores únicos é baixa (padrão: menos de 50% das linhas).
    Isso evita transformar colunas de texto livre (nomes, descrições
    longas e praticamente únicas) em categoria, o que pioraria a memória
    em vez de melhorar.
    """
    colunas_object = df.select_dtypes(include=['object']).columns
    total_linhas = len(df)

    for col in colunas_object:
        n_unicos = df[col].nunique(dropna=True)
        if total_linhas > 0 and (n_unicos / total_linhas) < limite_cardinalidade:
            df[col] = df[col].astype('category')

    return df


def otimizar_dataframe(df: pd.DataFrame, nome: str = '', verbose: bool = True) -> pd.DataFrame:
    """
    Aplica downcast numérico + categórico em um DataFrame e reporta o
    ganho de memória. Funciona em qualquer tabela do projeto (dimensão
    ou fato) porque varre os dtypes existentes, sem lista fixa de colunas.
    """
    mem_antes = _memoria_mb(df)

    df = downcast_numericos(df)
    df = downcast_categoricos(df)

    if verbose:
        mem_depois = _memoria_mb(df)
        reducao = (1 - mem_depois / mem_antes) * 100 if mem_antes > 0 else 0
        print(f"📉 {nome or 'DataFrame'}: {mem_antes:.2f} MB -> {mem_depois:.2f} MB (-{reducao:.1f}%)")

    return df


def reverter_categoricos_para_texto(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converte colunas 'category' de volta para string antes de gravar no
    Postgres/Supabase. Algumas engines/tipos SQLAlchemy não lidam bem com
    o dtype category do pandas na hora do to_sql — usar isso logo antes
    do load_dataframe evita erro de tipo na carga.
    """
    colunas_categoricas = df.select_dtypes(include=['category']).columns
    for col in colunas_categoricas:
        df[col] = df[col].astype(str)
    return df