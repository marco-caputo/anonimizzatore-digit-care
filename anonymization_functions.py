from typing import Iterable
from multiprocessing import Pool

import spacy
from spacy import Language

from config import DEFAULT_NER_MODEL, DEFAULT_ENTITIES, DEFAULT_EXTRA_PER_MATCHING_LEVEL, SINGLE_TEXT_FIELDS, MULTI_PROCESSING, P_CORES
from evaluation.compute_metrics import compute_metrics_from_spacy_docs, infer_predicted_spans
from rules.rules import apply_rules
from utils.anonymization_utils import anonymize_doc, get_entity_spans_from_metadata
from utils.multiprocessing_utils import estimate_spacy_params
from utils.path_utils import get_resource_path

# ----------------------------
#   Anonymization Function
# ----------------------------
def anonymize(text: str,
              nlp:Language = None,
              entities:Iterable[str]=None,
              per_matching:bool=None,
              personal_data:dict[str, str]=None) -> str:
    """
    Anonymizes the input text by replacing entities with placeholders only for the specified entity types,
    or the default ones if none are specified.

    :param text: Input text to anonymize.
    :param nlp: pre-loaded spaCy Language model. If None, loads the default
    :param entities: List of entity types to anonymize.
    :param per_matching: Whether to anonymize PER and PATIENT entities in combination with dictionaries or not.
    :param personal_data: Dictionary of specific personal data to anonymize.
    """
    if nlp is None: nlp = spacy.load(DEFAULT_NER_MODEL)
    if entities is None: entities = DEFAULT_ENTITIES
    if per_matching is None: per_matching = DEFAULT_EXTRA_PER_MATCHING_LEVEL

    return anonymize_doc(apply_rules(nlp(text), per_matching, personal_data), entities)

def anonymize_texts(texts: list[str],
                    nlp: Language = None,
                    entities: Iterable[str] = None,
                    per_matching: int = None,
                    personal_data: list[dict[str, str]] = None,
                    meta_data: list[dict] = None,
                    multi_processing: bool = MULTI_PROCESSING,
                    p_cores: int = P_CORES) -> tuple[list[str], dict[str, dict[str, float]] | None]:
    """
    Applies the anonymization function to a list of texts with optional personal data and metadata.
    If metadata is provided and contains entity information, it is used to extract gold entities and apply evaluation.

    :param texts: the list of original texts to anonymize
    :param nlp: pre-loaded spaCy Language model. If None, loads the default
    :param entities: list of entity types to anonymize.
    :param per_matching: whether to anonymize PER and PATIENT entities in combination with dictionaries or not.
    :param personal_data: list of dictionaries of specific personal data to anonymize for each text.
    :param meta_data: list of metadata dictionaries for each text, used for evaluation if they contain entity information.
    :param multi_processing: whether to use multi-processing for anonymization or not.
    :param p_cores: number of performance CPU cores to use for multi-processing, if it is set to True.
    :return: a tuple containing the list of anonymized texts and a dictionary of evaluation metrics (if metadata is provided)
    """
    if nlp is None: nlp = spacy.load(get_resource_path(DEFAULT_NER_MODEL))
    if entities is None: entities = DEFAULT_ENTITIES
    if per_matching is None: per_matching = DEFAULT_EXTRA_PER_MATCHING_LEVEL

    if multi_processing:
        n_processes, batch_size = estimate_spacy_params(texts, p_cores)
        anonymized_docs = nlp.pipe(texts, n_process=n_processes, batch_size=batch_size)
    else:
        anonymized_docs = [nlp(text) for text in texts]

    if multi_processing:
        with Pool(processes=p_cores) as pool:
            pred_docs = pool.starmap(apply_rules,
                [(doc, per_matching, per_data) for doc, per_data in zip(anonymized_docs, personal_data)]
            )
    else:
        pred_docs = [apply_rules(doc, per_matching, per_data) for doc, per_data in zip(anonymized_docs, personal_data)]

    anonymized_texts = [anonymize_doc(doc, entities) for doc in pred_docs]
    metrics = None

    # If entity metadata is provided, extract gold entities for evaluation
    pred_docs_eval = []
    if meta_data is not None and any([(SINGLE_TEXT_FIELDS[-1] in meta and meta[SINGLE_TEXT_FIELDS[-1]] is not None) for meta in meta_data]):
        gold_docs = []
        for text, meta, pred_doc_eval in zip(texts, meta_data, pred_docs):
            if meta[SINGLE_TEXT_FIELDS[-1]] is not None or meta[SINGLE_TEXT_FIELDS[-2]] is not None:
                gold_docs.append({"text": text, "entities":
                    get_entity_spans_from_metadata(text, meta[SINGLE_TEXT_FIELDS[-1]]) if meta[SINGLE_TEXT_FIELDS[-1]] is not None
                    else infer_predicted_spans(text, meta[SINGLE_TEXT_FIELDS[-2]])
                })
                pred_docs_eval.append(pred_doc_eval)
        metrics = compute_metrics_from_spacy_docs(gold_docs, pred_docs_eval, entities)

    return anonymized_texts, metrics


def get_full_labeller(path: str = DEFAULT_NER_MODEL, per_matching:int=DEFAULT_EXTRA_PER_MATCHING_LEVEL):
    """Returns a full anonymization function using the specified spaCy model path."""
    nlp = spacy.load(get_resource_path(path))
    return lambda text: apply_rules(nlp(text), per_matching)