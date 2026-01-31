SELECT 	 
	 [Aul_Ts_Zeit]
	,CrefoIdDelete = [Aul_Vc_Objekt]  --Wird gelöscht (bekommt Sperrcode XX)
	,CrevoIdSurvive = convert(int,RIGHT(l.Aul_Vc_Text,9)) --überlebendes Archiv
FROM [CnZenReport].[dbo].[Audit_Log] l
where 1=1
and l.Aul_Ben_Vc_Mkz = 'ZDSNECL' --unsere Zusammenlegerin
and l.Aul_Vc_Text LIKE 'Delete aus Zusammenführung%'


/*
SELECT P.Pa_L_Nr,P.Pa_S_SperrCode FROM CnZenReport.dbo.Pool_Adresse P
/*Aul_Vc_Objekt (Sperrcode XX),Aul_Vc_Text = Delete aus Zusammenführung (Keep)*/
WHERE P.Pa_L_Nr in (427686423, 425588399)
*/