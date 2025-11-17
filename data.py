
#%%
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import matplotlib.pyplot as plt

### Umgebungsvariablen
driver = 'ODBC Driver 17 for SQL Server'
server = 'PRODSVCREPORT70'
db = 'CAG_Analyse'

### Hilfsfunktionen
def conn_string_sql_alchemy(server, db, driver):
    conn_string = f'mssql://{server}/{db}?trusted_connection=yes&driver={driver}'
    return conn_string 
    
def erzeuge_engine_von_conn_string_sql_alchemy(conn_string):
    try:
        engine = create_engine(conn_string)
        with engine.connect() as conn:
            print("")
        return engine
    except Exception as e:
        print(f"Es gab einen Fehler beim Verbinden: {e}")
        return None

def schliess_engine(engine):
    engine.dispose()

def lade_daten(engine,query):
    query_resultat = pd.DataFrame(engine.connect().execute(text(query)))
    return query_resultat

conn_string = conn_string_sql_alchemy(server, db, driver)
engine = erzeuge_engine_von_conn_string_sql_alchemy(conn_string)
print(conn_string)


query = """
SELECT TOP (1000) [Name]
      ,[Vorname]
      ,[Name2]
      ,[Strasse]
      ,[HausNummer]
      ,[Plz]
      ,[Ort]
      ,[Crefo]
      ,[Geburtstag]
      ,[Jahrgang]
      ,[Erfasst]
      ,[Quelle_95]
  FROM [CAG_Analyse].[dbo].[vAdresse_Quelle95]
  Where Erfasst < dateadd(day,-7,getdate())
"""
df = lade_daten(engine,query)
# %%
df.head()