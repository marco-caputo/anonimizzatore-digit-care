import json
import os
from typing import Iterable

from spacy.tokens import Doc
from docx import Document
from PyPDF2 import PdfReader

from config import PATIENT_DATA_FIELDS, SINGLE_TEXT_FIELDS, DEFAULT_OUTPUTS_IN_SINGLE_FILE, SINGLE_ENTITY_FIELDS, \
    PERSONAL_DATA_FIELDS
from utils.json_utils import read_json_file, save_json_file
from utils.path_utils import get_file_name_from_anagrafica

TEXT = SINGLE_ENTITY_FIELDS[0]
START = SINGLE_ENTITY_FIELDS[1]
END = SINGLE_ENTITY_FIELDS[2]
LABEL = SINGLE_ENTITY_FIELDS[3]

def anonymize_doc(doc: Doc, labels_to_anonymize: Iterable[str]=None) -> str:
    """
    Returns anonymized text where selected entity labels are replaced by [LABEL].

    :param doc: spaCy Doc
    :param labels_to_anonymize: Iterable of entity labels to anonymize (e.g. {"PER", "LOC"})
                                If None, anonymizes ALL entities.
    """
    labels_to_anonymize = set(ent.label_ for ent in doc.ents) if labels_to_anonymize is None else set(labels_to_anonymize)
    text = doc.text

    # collect only entities whose label is in the allowed set
    offsets = [(ent.start_char, ent.end_char, ent.label_) for ent in doc.ents if ent.label_ in labels_to_anonymize]
    offsets.sort(reverse=True) # Replace from end to beginning to preserve offsets

    for start, end, label in offsets:
        text = text[:start] + f"[{label}]" + text[end:]

    return text

def get_entity_spans_from_metadata(original_text:str, metadata_entities: list[dict]) -> Iterable[str]:
    """Extracts entity spans from metadata entity list."""
    entity_spans = []

    for entity in metadata_entities:
        if START in entity and END in entity and LABEL in entity:
            entity_spans.append((entity[START], entity[END], entity[LABEL]))
        elif TEXT in entity and LABEL in entity:
            start = original_text.find(entity[TEXT])
            if start != -1:
                end = start + len(entity[TEXT])
                entity_spans.append((start, end, entity[LABEL]))
    return entity_spans

def save_anonymized_text(text:str, output_path=None, output_dir=None, original_filename=None) -> str:
    """Saves anonymized text to a .txt file and returns the output path."""
    if output_path:
        out_path = output_path
    elif output_dir and original_filename:
        base_name = os.path.splitext(os.path.basename(original_filename))[0]
        out_path = os.path.join(output_dir, f"{base_name}_anonymized.txt")
    else:
        raise ValueError("Must specify either output_path or output_dir")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return out_path

def save_metrics(metrics: dict, output_path=None, output_dir=None, original_filename=None) -> str:
    """Saves metrics dictionary to a JSON file and returns the output path."""
    if output_path:
        out_path = output_path
    elif output_dir and original_filename:
        base_name = os.path.splitext(os.path.basename(original_filename))[0]
        out_path = os.path.join(output_dir, f"{base_name}_metrics.json")
    else:
        raise ValueError("Must specify either output_path or output_dir")

    save_json_file(out_path, metrics)
    return out_path

def save_many_texts(texts: list[str],
                    output_dir: str,
                    original_filename: str = None,
                    single_file: bool=DEFAULT_OUTPUTS_IN_SINGLE_FILE,
                    metadata:list[dict] = None,
                    personal_data:list[dict] = None) -> str:
    """Saves multiple anonymized documents in the specified directory.
    If the single_file flag is True, texts related to the same patient are saved in a single json file,
    otherwise as separate .txt files.
    In case of single json files for each identity, metadata is also saved if provided.

    :params texts: list of string texts to anonymize
    :param output_dir: directory where to save the anonymized files
    :param original_filename: the original file name (used to derive output file names if output_path is not provided)
    :param single_file: if True, saves all texts of the same patient in a single JSON file; if False, saves each text in a separate .txt file
    :param metadata: optional list of metadata dictionaries corresponding to each text (used only if single_file is True)
    :param personal_data: optional list of personal data dictionaries corresponding to each text (used only if single_file is True)
    :returns: the path to the saved file directory
    """
    os.makedirs(output_dir, exist_ok=True)

    if personal_data is not None:
        base_names = [entry.get(PERSONAL_DATA_FIELDS[8], f"dict_{json.dumps(entry, sort_keys=True)}") if entry else f"text_{i+1}"
                      for i, entry in enumerate(personal_data)]
    else:
        base_names = [f"text_{i+1}" for i in range(len(texts))]

    # Multiple texts → multiple files
    if not single_file:
        written_files = []
        for i, (text, base_name) in enumerate(zip(texts, base_names)):
            out_path = os.path.join(output_dir, f"{base_name}_anonymized_{i+1}.txt")
            save_anonymized_text(text, output_path=out_path)
            written_files.append(out_path)

        return output_dir

    # Multiple texts → single JSON
    if metadata:
        unlabelled_metadata = [{field: meta[field] for field in SINGLE_TEXT_FIELDS[:-3]} for meta in metadata]
        text_data = [{**meta, **{SINGLE_TEXT_FIELDS[2]: text}} for text, meta in zip(texts, unlabelled_metadata)]
    else:
        text_data = list(texts)

    if personal_data:
        out_paths = []
        for base_name in set(base_names):
            indeces = [i for i in range(len(personal_data))
                       if (personal_data[i].get(PERSONAL_DATA_FIELDS[8], f"dict_{json.dumps(personal_data[i], sort_keys=True)}")
                           if personal_data[i] else f"text_{i+1}") == base_name]
            patient_data = {
                    PERSONAL_DATA_FIELDS[8]: base_name if isinstance(base_name, int) else None,
                    PERSONAL_DATA_FIELDS[1]: [text_data[i] for i in indeces]
            }

            base_file_name = os.path.splitext(os.path.basename(original_filename))[0] \
                if original_filename is not None else base_name

            file_name = f"{base_file_name}_anonymized.json" if not str(base_file_name).startswith("dict_") \
                else get_file_name_from_anagrafica({}, add_random_suffix=True)
            out_paths.append(os.path.join(output_dir, file_name))
            save_json_file(out_paths[-1], patient_data)
        return output_dir

    else:
        base_file_name = os.path.splitext(os.path.basename(original_filename))[0] \
            if original_filename is not None else base_names[0]

        out_path = os.path.join(output_dir, f"{base_file_name}_anonymized.json")
        save_json_file(out_path, text_data)
        return output_dir


def read_file(file_path) -> tuple[list[str], list[dict[str,str]]|None, dict[str,str]|None]:
    """Reads a file and returns its text content in form of a list strings combined with optional list of dictionaries
    of metadata and a dictionary of personal data."""
    ext = os.path.splitext(file_path)[1].lower()
    metadata = []
    personal_data = None

    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            texts = [f.read()]
    elif ext == ".docx":
        doc = Document(file_path)
        texts = ["\n".join([para.text for para in doc.paragraphs])]
    elif ext == ".pdf":
        reader = PdfReader(file_path)
        texts = ["\n".join([page.extract_text() or "" for page in reader.pages])]
    elif ext == ".json":
        data = read_json_file(file_path)
        try:
            texts = [text[SINGLE_TEXT_FIELDS[2]] for text in data[PATIENT_DATA_FIELDS[1]]]
        except IndexError:
            raise ValueError(f"JSON file must contain a '{PATIENT_DATA_FIELDS[1]}' field consisting in a list of entries with '{SINGLE_TEXT_FIELDS[1]}' fields.")

        for text in data[PATIENT_DATA_FIELDS[1]]:
            meta = {field: text.get(field, None) for field in SINGLE_TEXT_FIELDS if field != SINGLE_TEXT_FIELDS[2]}
            metadata.append(meta)

        if PATIENT_DATA_FIELDS[0] in data: personal_data = data[PATIENT_DATA_FIELDS[0]]
    else:
        raise ValueError("Unsupported file type.")

    return texts, metadata, personal_data
