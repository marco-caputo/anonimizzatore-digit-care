### IMPOSTAZIONI GENERALI

DEFAULT_NER_MODEL = "NER/models/deployed/deployed_v2.2"
DEFAULT_ENTITIES = ["PATIENT", "PER", "LOC", "ORG", "FAC", "GPE", "PROV", "DATE", "EVENT", "NORP", "AGE", "CODE", "MAIL", "PHONE", "URL"]
DEFAULT_EXTRA_PER_MATCHING_LEVEL = 0            # Whether to use extra pattern matching for PERSON entities (in addition to NER), in particular:
                                                # 0: no extra matching,
                                                # 1: match non-ambiguous names and surnames when they appear as names (capitalized/uppercase and not preceded by a preposition),
                                                # 2: match non-ambiguous names in any case and ambiguous names and surnames when they appear as names (capitalized/uppercase and not preceded by a preposition)
DEFAULT_OUTPUTS_IN_SINGLE_FILE = True           # True: If multiple texts are found in a json, save them in a single json file; False: save each text in a separate .txt file

### IMPOSTAZIONI PER IL MULTI-PROCESSING

MULTI_PROCESSING = False                        # Whether to use multiprocessing for anonymizing multiple texts
P_CORES = 4                                     # Number of Cores / Performance Cores of the machine (used for multiprocessing)

### FORMATO DEI JSON DI INPUT

PATIENT_DATA_FIELDS = [
    "anagrafica",               # Dizionario con i dati anagrafici del paziente, segue la struttura di PERSONAL_DATA_FORMAT
    "testi"                     # Lista di dizionari con i testi associati al paziente, i singoli dizionari seguono la struttura di SINGLE_TEXT_FIELDS
]
SINGLE_TEXT_FIELDS = [
    "tipo",                     # Stringa che indica il tipo di testo (es. "Diario terapeutico", "Relazione periodica", ecc.)
    "data",                     # Stringa che indica la data del testo (es. "2023-01-15")
    "testo",                    # Stringa con il testo originale
    "testo_anonimizzato",       # Stringa con il testo anonimizzato (opzionale, usato per scopi di testing, alternativo a "lista_entita")
    "lista_entita"              # Lista di dizionari con le entità presenti nel testo, i singoli dizionari seguono la struttura di SINGLE_ENTITY_FIELDS (opzionale, usato per scopi di testing, alternativo a "testo_anonimizzato")
]
PERSONAL_DATA_FIELDS = [
    "nome",
    "cognome",
    "nazione_nascita",
    "luogo_nascita",
    "data_nascita",
    "nazione_residenza",
    "luogo_residenza",
    "prov_residenza",
    "idAna"
]
PERSONAL_DATA_FORMAT = {
    PERSONAL_DATA_FIELDS[0] : "PATIENT",            # Nome del paziente
    PERSONAL_DATA_FIELDS[1] : "PATIENT",            # Cognome del paziente
    PERSONAL_DATA_FIELDS[2] : "GPE",                # Nazione di nascita
    PERSONAL_DATA_FIELDS[3] : "GPE",                # Luogo di nascita
    PERSONAL_DATA_FIELDS[4] : "DATE",               # Data di nascita
    PERSONAL_DATA_FIELDS[5] : "GPE",                # Nazione di residenza
    PERSONAL_DATA_FIELDS[6] : "GPE",                # Luogo di residenza
    PERSONAL_DATA_FIELDS[7] : "PROV"                # Sigla della provincia di residenza
}
SINGLE_ENTITY_FIELDS = [
    "testo",                    # Stringa che rappresenta il frammento di testo dell'entità (alternativo a "inizio" e "fine")
    "inizio",                   # Indice di inizio dell'entità nel testo (0-based, primo indice incluso e secondo escluso)
    "fine",                     # Indice di fine dell'entità nel testo (0-based, primo indice incluso e secondo escluso)
    "label"                     # Etichetta dell'entità (es. "PATIENT", "DATE", ecc.)
]