from __future__ import annotations

from typing import Iterator, Optional
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from urllib.parse import quote_plus

from .config import DbConfig


def get_engine(server: str, database: str, user: str = "", password: str = "") -> Engine:
    """
    Helper function to create a database engine from connection parameters.
    
    Args:
        server: SQL Server hostname
        database: Database name
        user: Username (optional, will use Windows Auth if empty)
        password: Password (optional, will use Windows Auth if empty)
    
    Returns:
        SQLAlchemy Engine
    """
    cfg = DbConfig(
        server=server,
        database=database,
        user=user or "WIN_AUTH",
        password=password or "",
        driver="ODBC Driver 17 for SQL Server",
        encrypt=False,
        trust_server_certificate=True,
    )
    return create_mssql_engine(cfg)


def create_mssql_engine(cfg: DbConfig) -> Engine:
    # Support Windows Authentication if user/password are empty or "WIN_AUTH"
    use_windows_auth = not cfg.user or not cfg.password or cfg.user.upper() == "WIN_AUTH"
    
    if use_windows_auth:
        odbc = (
            f"DRIVER={{{cfg.driver}}};"
            f"SERVER={cfg.server};DATABASE={cfg.database};"
            f"Trusted_Connection=yes;"
            f"Encrypt={'yes' if cfg.encrypt else 'no'};"
            f"TrustServerCertificate={'yes' if cfg.trust_server_certificate else 'no'};"
        )
    else:
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
