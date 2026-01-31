Select 
	 Crefo1 = m.I_Arc_Lfnr
	,Crefo2 = ISNULL(m.I_Mitglied_Nr, try_convert(int,V_Informant))
	,m.D_Material_Datum
from(
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY I_Arc_Lfnr ORDER BY D_Material_Datum DESC) AS RN
    FROM Arc_Mutations_Info m
    WHERE m.S_Material_Code = 95
	) m
	--ON m.I_Arc_Lfnr = p.Pa_L_Nr
	Where 1=1
		AND m.RN = 1