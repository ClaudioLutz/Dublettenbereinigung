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
      ,p.Pa_S_Anrede
  FROM [CAG_Analyse].[dbo].[vAdresse_Quelle95] v
  INNER JOIN CnZenReport.dbo.Pool_Adresse p
    ON v.Crefo = p.Pa_L_Nr
  ORDER BY PLZ,Strasse desc