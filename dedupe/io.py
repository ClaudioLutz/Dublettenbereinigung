from __future__ import annotations

from typing import Iterator, Optional
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from urllib.parse import quote_plus

from .config import DbConfig


def create_mssql_engine(cfg: DbConfig) -> Engine:
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
