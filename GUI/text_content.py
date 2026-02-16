from config import PERSONAL_DATA_FIELDS, PATIENT_DATA_FIELDS, SINGLE_TEXT_FIELDS, SINGLE_ENTITY_FIELDS

LEGEND = """
I formati accettati in input sono .txt, .docx, .pdf e .json. 
I file JSON devono seguire la seguente struttura:

LEGENDA:
    < . >       Opzionale
    ( . | . )   Alternativa
    [ . ]       Array
    ...         Ripetizione
"""

JSON_EXAMPLE = f"""

{{
    <"{PATIENT_DATA_FIELDS[0]}": 
	{{
        "{PERSONAL_DATA_FIELDS[0]}": string,
        "{PERSONAL_DATA_FIELDS[1]}": string,
        "{PERSONAL_DATA_FIELDS[2]}": string,
        "{PERSONAL_DATA_FIELDS[3]}": string,
        "{PERSONAL_DATA_FIELDS[4]}": string,
        "{PERSONAL_DATA_FIELDS[5]}": string,
        "{PERSONAL_DATA_FIELDS[6]}": string,
        "{PERSONAL_DATA_FIELDS[7]}": string,
        "{PERSONAL_DATA_FIELDS[8]}": int
    }},>
    "{PATIENT_DATA_FIELDS[1]}": [
        ({{
            <"{SINGLE_TEXT_FIELDS[0]}": string,>
            <"{SINGLE_TEXT_FIELDS[1]}": string,>		
            "{SINGLE_TEXT_FIELDS[2]}": string,
	    <"{SINGLE_TEXT_FIELDS[4]}": [
		{{
		     "{SINGLE_ENTITY_FIELDS[0]}": string,
		     "{SINGLE_ENTITY_FIELDS[3]}": string
		}} | 
		{{
		     "{SINGLE_ENTITY_FIELDS[1]}": integer,
		     "{SINGLE_ENTITY_FIELDS[2]}": integer,
		     "{SINGLE_ENTITY_FIELDS[3]}": string
		}}),
		...
	    ],>
	<"{SINGLE_TEXT_FIELDS[3]}": string>
        }},
        ...
    ]
}}
"""

METRICS_EXPLAINATION = """
Le metriche riportate misurano la qualità dell'anonimizzazione confrontando le entità individuate dal sistema con quelle attese.

• Precision:
Indica la proporzione di entità identificate correttamente rispetto al totale delle entità rilevate dal sistema. Valori alti indicano pochi falsi positivi.

• Recall:
Indica la proporzione di entità correttamente identificate rispetto al totale delle entità che avrebbero dovuto essere rilevate. Valori bassi indicano la presenza di falsi negativi.

• Coverage:
Misura quanto efficacemente il sistema riesce a coprire tutte le informazioni sensibili, anche a costo di anonimizzare più del necessario. È la metrica di interesse per valutare la protezione della privacy.

• F1-score:
È la media armonica tra precision e recall. Fornisce una misura sintetica dell'equilibrio tra accuratezza e copertura.

• Metriche aggregate (averages):
    - micro: calcolata globalmente sommando tutti i contributi delle entità.
    - macro: media semplice delle metriche calcolate per ciascuna etichetta.
    - weighted: media pesata in base alla frequenza delle etichette.

• ENT
La voce ENT rappresenta una valutazione globale in cui tutte le entità sono considerate come appartenenti a un'unica categoria. In questo caso non viene fatta distinzione tra le diverse etichette (PER, AGE, LOC, ecc.), ma si valuta la capacità complessiva del sistema di individuare correttamente qualsiasi entità trascurando la specifica tipologia.
"""
