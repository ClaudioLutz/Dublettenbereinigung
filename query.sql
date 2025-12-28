SELECT 
       [Name]
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
  where Plz like '8%'
  ORDER BY PLZ,Strasse desc