from data_generation.config import ENTITIES_NER, ENTITIES_POST, SEED_SAMPLES

NER_LABELS = [ent["label"] for ent in ENTITIES_NER]
POST_LABELS = [ent["label"] for ent in ENTITIES_POST]
ANONYMIZATION_LABELS = NER_LABELS + POST_LABELS