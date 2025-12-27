from __future__ import annotations

from typing import Iterator, Optional
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from urllib.parse import quote_plus

from .config import DbConfig


def create_mssql_engine(cfg: DbConfig) -> Engine:
<<<<<<< HEAD
    # Support Windows Authentication if user/password are empty or "WIN_AUTH"
    use_windows_auth = not cfg.user or not cfg.password or cfg.user.upper() == "WIN_AUTH"
    
    if use_windows_auth:
=======
    # Check if Windows Authentication (empty user/password)
    if not cfg.user and not cfg.password:
        # Windows Authentication
>>>>>>> 60fea81b9feec9ada01b362be681d2b95cad2049
        odbc = (
            f"DRIVER={{{cfg.driver}}};"
            f"SERVER={cfg.server};DATABASE={cfg.database};"
            f"Trusted_Connection=yes;"
            f"Encrypt={'yes' if cfg.encrypt else 'no'};"
            f"TrustServerCertificate={'yes' if cfg.trust_server_certificate else 'no'};"
        )
    else:
<<<<<<< HEAD
=======
        # SQL Server Authentication
>>>>>>> 60fea81b9feec9ada01b362be681d2b95cad2049
        odbc = (
            f"DRIVER={{{cfg.driver}}};"
            f"SERVER={cfg.server};DATABASE={cfg.database};UID={cfg.user};PWD={cfg.password};"
            f"Encrypt={'yes' if cfg.encrypt else 'no'};"
            f"TrustServerCertificate={'yes' if cfg.trust_server_certificate else 'no'};"
        )
    conn_str = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc)}"
    return create_engine(conn_str, pool_pre_ping=True, fast_executemany=False)


def read_sql_df(
    engine: Engine, query: str, *, chunksize: Optional[int] = None
) -> pd.DataFrame | Iterator[pd.DataFrame]:
    if chunksize:
        return pd.read_sql_query(query, engine, chunksize=chunksize)
    return pd.read_sql_query(query, engine)
