#%%
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

### Umgebungsvariablen
driver = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
server = os.getenv('DB_SERVER', 'PRODSVCREPORT70')
db = os.getenv('DB_DATABASE', 'CAG_Analyse')

### Hilfsfunktionen
def conn_string_sql_alchemy(server, db, driver):
    # Ensure driver has + in spaces if needed by SQLAlchemy URL format,
    # but for mssql+pyodbc usually it's passed as param.
    # However, existing code used mssql://...&driver=...
    # Depending on sqlalchemy version, mssql+pyodbc:// is preferred.
    # I will stick to existing format if it works, but parameterized properly.
    # Actually, let's keep it close to original but cleaner.
    conn_string = f'mssql://{server}/{db}?trusted_connection=yes&driver={driver}'
    return conn_string

def erzeuge_engine_von_conn_string_sql_alchemy(conn_string):
    try:
        engine = create_engine(conn_string)
        # Verify connection
        with engine.connect() as conn:
            pass
        return engine
    except Exception as e:
        print(f"Es gab einen Fehler beim Verbinden: {e}")
        return None

def schliess_engine(engine):
    engine.dispose()

def lade_daten(engine, query):
    if engine is None:
        raise ValueError("Engine object is None")
    # Using 'with' to ensure connection closure is handled by SQLAlchemy context if possible,
    # but engine.connect() returns a connection.
    with engine.connect() as conn:
        query_resultat = pd.read_sql(text(query), conn)
    return query_resultat

def get_engine():
    """Helper to get the configured engine."""
    conn_string = conn_string_sql_alchemy(server, db, driver)
    return erzeuge_engine_von_conn_string_sql_alchemy(conn_string)
