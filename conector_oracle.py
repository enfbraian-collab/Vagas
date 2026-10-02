# OracleConnector.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
import pandas as pd
from typing import Optional
from sqlalchemy.engine import URL

load_dotenv()

class OracleConnector:
    def __init__(self):
        self.user = os.getenv('ORACLE_USER')
        self.password = os.getenv('ORACLE_PASSWORD')
        self.host = os.getenv('ORACLE_HOST')
        self.port = os.getenv('ORACLE_PORT')
        self.service_name = os.getenv('ORACLE_SERVICE_NAME')
        self.schema = os.getenv('ORACLE_SCHEMA')
        self.engine = None 
        
    def conectar(self):
        try:
            connection_url = URL.create(
                "oracle+oracledb",
                username=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                query={"service_name": self.service_name}
            )
            self.engine = create_engine(connection_url)
            
            with self.engine.connect() as conns:
                pass
                
            print("✅ Conexão com Oracle realizada com sucesso!")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao conectar no Oracle: {e}")
            return False

    def _limpar_encoding(self, df: pd.DataFrame) -> pd.DataFrame:
        """Método interno que limpa automaticamente caracteres corrompidos (como o [E7])"""
        for col in df.select_dtypes(include=['object']):
            df[col] = df[col].apply(lambda x: 
                x.encode('latin1', errors='ignore').decode('utf-8', errors='ignore') 
                if isinstance(x, str) else x
            )
        return df

    def executar_query(self, query: str, chunksize: Optional[int] = None) -> pd.DataFrame:
        if not self.engine:
            print("⚠️ Você precisa chamar .conectar() primeiro!")
            return pd.DataFrame()
        
        try:
            print("🔄 Executando query...")
            df = pd.read_sql(query, self.engine, chunksize=chunksize)
            
            if isinstance(df, pd.DataFrame):
                df_final = df
            else:
                df_list = list(df)
                df_final = pd.concat(df_list, ignore_index=True)
            
            # 🛡️ LIMPEZA AUTOMÁTICA APLICADA AQUI
            df_final = self._limpar_encoding(df_final)
            
            print(f"✅ Query executada com sucesso! Total de linhas: {len(df_final)}")
            return df_final
                
        except Exception as e:
            print(f"❌ Erro ao executar query: {e}")
            return pd.DataFrame()

    def fechar_conexao(self):
        if self.engine:
            self.engine.dispose()
            print("🔌 Conexão encerrada.")


