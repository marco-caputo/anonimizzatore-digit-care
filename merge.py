#!/usr/bin/env python3

import os
import argparse

from config import PATIENT_DATA_FIELDS
from utils import read_json_file, save_json_file
from utils.path_utils import get_file_name_from_anagrafica

# ----------------------------
#   Merge Lambda
# ----------------------------
def merge(folder: str) -> None:
    """
    Merges patient JSON files in the specified folder based on their anagrafica information.
    Files with matching or subset anagrafica are combined into a single file, consolidating their text entries and
    keeping the most complete anagrafica. After merging, old files are removed and new merged files are saved with
    names derived from the anagrafica.

    :param folder: Path to the folder containing patient JSON files to be merged. Each file should contain an anagrafica and a list of text entries.
    """
    patients = load_json_files(folder)

    merged = []

    for path, data in patients:
        current_ana = data[PATIENT_DATA_FIELDS[0]] if PATIENT_DATA_FIELDS[0] in data else {}
        current_testi = data[PATIENT_DATA_FIELDS[1]]

        found_group = False

        for group in merged:
            if anagrafica_match(group[PATIENT_DATA_FIELDS[0]], current_ana):
                group[PATIENT_DATA_FIELDS[1]].extend(current_testi)  # merge texts
                group[PATIENT_DATA_FIELDS[0]] = merge_anagrafica(group[PATIENT_DATA_FIELDS[0]],
                                                                 current_ana)  # keep most complete anagrafica
                found_group = True
                break

        if not found_group:
            merged.append({
                PATIENT_DATA_FIELDS[0]: current_ana,
                PATIENT_DATA_FIELDS[1]: current_testi.copy()
            })

    for path, _ in patients: os.remove(path)  # Remove old files

    for patient in merged:  # Save merged files
        file_name = get_file_name_from_anagrafica(patient[PATIENT_DATA_FIELDS[0]], add_random_suffix=False)
        output_path = os.path.join(folder, file_name)
        save_json_file(output_path, patient)

    print(f"Merged into {len(merged)} patient files.")

def is_subset_dict(d1, d2):
    """
    Returns True if d1 is a subset of d2
    (all keys of d1 exist in d2 with same values)
    """
    return all(k in d2 and d2[k] == v for k, v in d1.items())


def anagrafica_match(a1, a2):
    """
    Two anagrafica match if:
    - exactly equal OR
    - one is subset of the other
    """
    return a1 == a2 or is_subset_dict(a1, a2) or is_subset_dict(a2, a1)


def merge_anagrafica(a1, a2):
    """Return a new anagrafica with all fields from both. All common fields should have the same value,
    otherwise we keep the one from the longer anagrafica."""
    merged = a1.copy()
    for k, v in a2.items():
        if k not in merged:
            merged[k] = v
        elif merged[k] != v:
            if len(a2) > len(a1): # Conflict: keep value from longer anagrafica
                merged[k] = v
    return merged


def load_json_files(folder):
    patients = []
    for filename in os.listdir(folder):
        if filename.lower().endswith(".json"):
            path = os.path.join(folder, filename)
            data = read_json_file(path)
            if PATIENT_DATA_FIELDS[0] in data and PATIENT_DATA_FIELDS[1] in data:
                patients.append((path, data))
    return patients


def main():
    parser = argparse.ArgumentParser(description="Merge patient JSON files.")
    parser.add_argument("folder", help="Folder containing patient JSON files")
    args = parser.parse_args()

    merge(args.folder)

if __name__ == "__main__":
    main()
