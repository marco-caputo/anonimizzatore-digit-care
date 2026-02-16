import sys
import uuid
from pathlib import Path

from config import PERSONAL_DATA_FIELDS

def get_resource_path(relative_path):
    PROJECT_ROOT = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parents[1]
    return PROJECT_ROOT / relative_path

def get_file_name_from_anagrafica(anagrafica, add_random_suffix=False):
    """
    Provides a safe filename based on the anagrafica information, prioritizing idAna, then cognome, and adding a
    random suffix if requested.

    :param anagrafica: Dictionary containing patient information, expected to have keys like 'idAna' or 'cognome'.
    :param add_random_suffix: Boolean flag to indicate whether to append a random suffix to the filename for uniqueness.
    :return: A string representing a safe filename derived from the anagrafica data, with a .json extension.
    """
    if PERSONAL_DATA_FIELDS[8] in anagrafica:
        name = f"{anagrafica[PERSONAL_DATA_FIELDS[8]]}"
    elif PERSONAL_DATA_FIELDS[1] in anagrafica:
        name = f"{anagrafica[PERSONAL_DATA_FIELDS[1]]}"
    else:
        name = "UNKNOWN"
    if add_random_suffix:
        random_suffix = uuid.uuid4().hex[:8]
        name += f"_{random_suffix}"
    safe_name = "".join(c if c.isalnum() else "_" for c in name.upper())

    return f"{safe_name}.json"