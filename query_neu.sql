use CnZenReport


Select 
       [Name]			= p.Pa_S_Name
      ,[Vorname]		= p.Pa_S_Vorname
      ,[Name2]			= p.Pa_S_Name2
      ,[Strasse]		= p.Pa_S_Strasse
      ,[HausNummer]		= p.Pa_S_HausNummer
      ,[Plz]			= p.Pa_S_Plz
      ,[Ort]			= p.Pa_S_Ort
      ,[Crefo]			= p.Pa_L_Nr
      ,[Geburtstag]		= p.Pa_D_Geburtstag
      ,[Jahrgang]		= p.Pa_L_Jahrgang
      ,[Erfasst]		= p.Pa_Dt_Erfasst
      ,[Quelle_95]		= case when m.I_Arc_Lfnr is null then 0 else 1 end
      ,p.Pa_S_Anrede
From Pool_Adresse p
LEFT JOIN (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY I_Arc_Lfnr ORDER BY D_Material_Datum DESC) AS RN
    FROM Arc_Mutations_Info m
    WHERE m.S_Material_Code = 95
	) m
	ON m.I_Arc_Lfnr = p.Pa_L_Nr
		AND m.RN = 1
WHERE p.Pa_S_Adrart = 'P'
    AND p.Pa_S_Adrtyp = 1
    AND p.Pa_S_Strasse IS NOT NULL
    AND p.Pa_S_Strasse != ''
    AND p.Pa_S_SperrCode != 'XX'
    AND p.Pa_N_Status = '70' 