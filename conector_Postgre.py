import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import URL

class SupabaseConnector:
    def __init__(self, env_path: str = '.env'):
        load_dotenv(env_path, override=True)
        self.user = os.getenv('SUPABASE_USER')
        self.password = os.getenv('SUPABASE_PASSWORD')
        self.host = os.getenv('SUPABASE_HOST')
        self.port = os.getenv('SUPABASE_PORT')
        self.db = os.getenv('SUPABASE_DB')
        
        self.engine = self._create_engine()

    def _create_engine(self):
        """Cria a engine do Postgres via SQLAlchemy com segurança."""
        connection_url = URL.create(
            drivername="postgresql+psycopg2",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.db
        )
        return create_engine(connection_url)
    
    def _sanitizar_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Garante que o DataFrame esteja em UTF-8 puro antes de subir para o Postgres"""
        df_clean = df.copy()
        for col in df_clean.select_dtypes(include=['object']):
            df_clean[col] = df_clean[col].apply(
                lambda x: x.encode('latin1', errors='ignore').decode('utf-8', errors='ignore') 
                if isinstance(x, str) else x
            )
        return df_clean

    def _tabela_existe(self, connection, table_name: str) -> bool:
        """Verifica se a tabela já existe no PostgreSQL"""
        inspector = inspect(connection)
        return inspector.has_table(table_name)

    def load_dataframe(self, df: pd.DataFrame, table_name: str, truncate_first: bool = True):
        """
        Carrega o DataFrame para o PostgreSQL garantindo a transação atômica.
        Se a tabela não existir, ela será criada automaticamente.
        """
        try:
            df_processado = self._sanitizar_dataframe(df)

            with self.engine.connect() as connection:
                with connection.begin():
                    # Executa o TRUNCATE apenas se a tabela já existir no banco
                    if truncate_first and self._tabela_existe(connection, table_name):
                        connection.execute(text(f'TRUNCATE TABLE "{table_name}";'))
                        
                    # Se a tabela não existir, o Pandas (to_sql) cria ela automaticamente
                    df_processado.to_sql(
                        name=table_name,
                        con=connection,
                        if_exists='append',
                        index=False,
                        chunksize=500,
                        method='multi'
                    )
            print(f"✅ Dados da tabela '{table_name}' carregados com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro crítico ao carregar a tabela {table_name}: {e}")
            raise e

    def load_incremental_por_data(self, df: pd.DataFrame, table_name: str, col_data: str, data_corte=None):
        """
        Realiza a carga incremental por data:
        Apaga do PostgreSQL os registros a partir da 'data_corte' (se a tabela existir)
        e insere os novos dados atualizados.
        """
        if df.empty:
            print(f"⚠️ DataFrame da tabela '{table_name}' está vazio. Carga ignorada.")
            return

        try:
            df_processado = self._sanitizar_dataframe(df)

            # Se data_corte não for passada, pega a menor data presente no lote
            if data_corte is None:
                data_corte = df_processado[col_data].min()

            if isinstance(data_corte, pd.Timestamp):
                data_corte = data_corte.strftime('%Y-%m-%d %H:%M:%S')

            with self.engine.connect() as connection:
                with connection.begin():
                    # Deleta apenas se a tabela já existir
                    if self._tabela_existe(connection, table_name):
                        sql_delete = f'DELETE FROM "{table_name}" WHERE "{col_data}" >= :data_corte;'
                        connection.execute(text(sql_delete), {"data_corte": str(data_corte)})
                    
                    # Insere os novos dados (criando a tabela se for a primeira vez)
                    df_processado.to_sql(
                        name=table_name,
                        con=connection,
                        if_exists='append',
                        index=False,
                        chunksize=1000,
                        method='multi'
                    )

            print(f"✅ Carga incremental concluída em '{table_name}' (registros >= {data_corte} atualizados)!")

        except Exception as e:
            print(f"❌ Erro na carga incremental da tabela {table_name}: {e}")
            raise e
    
    def fechar_conexao(self):
        """Fecha o pool de conexões do SQLAlchemy"""
        if self.engine:
            self.engine.dispose()
            print("🔌 Conexão encerrada.")