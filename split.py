#!/usr/bin/env python3

import os
import re
import argparse
import uuid
from collections import defaultdict

from utils import read_json_file, save_json_file
from config import PATIENT_DATA_FIELDS, PERSONAL_DATA_FIELDS, SINGLE_TEXT_FIELDS
from utils.path_utils import get_file_name_from_anagrafica

# ----------------------------
#   Split Lambda
# ----------------------------
def split(inputs: list[str], output_dir: str) -> None:
    """
    Splits patient JSON files into separate files based on surname fragments in text entries.
    Each text entry is analyzed for fragments starting with a surname followed by a colon, and these fragments are grouped by normalized surname.
    The resulting files contain the anagrafica of the patient (if available) and the corresponding text fragments.

    :param inputs: List of input JSON file paths or folder paths containing JSON files. Each file should contain an anagrafica and a list of text entries.
    :param output_dir: Path to the folder where the split patient JSON files will be saved. Each file will be named based on the patient's anagrafica or surname.
    """
    all_anagrafica = {}
    all_text_entries = []

    # --- Expand inputs (files + folders) ---
    expanded_files = []

    for path in inputs:
        if os.path.isdir(path):
            # Add all .json files in folder
            for filename in os.listdir(path):
                if filename.lower().endswith(".json"):
                    expanded_files.append(os.path.join(path, filename))
        elif os.path.isfile(path) and path.lower().endswith(".json"):
            expanded_files.append(path)
        else:
            print(f"Warning: '{path}' is not a valid JSON file or folder.")

    if not expanded_files:
        print("No valid JSON files found.")
        return

    # --- Parse input files ---
    for filepath in expanded_files:
        data = read_json_file(filepath)

        # Collect anagrafica
        if PATIENT_DATA_FIELDS[0] in data:
            for entry in data[PATIENT_DATA_FIELDS[0]]:
                if PERSONAL_DATA_FIELDS[1] in entry:
                    norm = normalize_surname(entry[PERSONAL_DATA_FIELDS[1]])
                    all_anagrafica[norm] = entry

        # Collect testi
        if PATIENT_DATA_FIELDS[1] in data:
            all_text_entries.extend(data[PATIENT_DATA_FIELDS[1]])

    # --- Group fragments per patient ---
    patient_data = defaultdict(list)

    for entry in all_text_entries:
        fragments = extract_fragments(entry.get(SINGLE_TEXT_FIELDS[2], ""))
        for surname_raw, content in fragments:
            norm_surname = normalize_surname(surname_raw)
            fragment_dict = {}
            if SINGLE_TEXT_FIELDS[0] in entry: fragment_dict[SINGLE_TEXT_FIELDS[0]] = entry[SINGLE_TEXT_FIELDS[0]]
            if SINGLE_TEXT_FIELDS[1] in entry: fragment_dict[SINGLE_TEXT_FIELDS[1]] = entry[SINGLE_TEXT_FIELDS[1]]
            fragment_dict[SINGLE_TEXT_FIELDS[2]] = content
            patient_data[norm_surname].append(fragment_dict)

    # --- Write output files ---
    os.makedirs(output_dir, exist_ok=True)
    for norm_surname, testi_list in patient_data.items():
        anagrafica_entry = all_anagrafica[norm_surname] if norm_surname in all_anagrafica else {"cognome": norm_surname}
        output_data = {
            PATIENT_DATA_FIELDS[0]: anagrafica_entry,
            PATIENT_DATA_FIELDS[1]: testi_list
        }

        output_path = get_file_name_from_anagrafica(anagrafica_entry, add_random_suffix=True)
        save_json_file(output_path, output_data)

    print(f"Created {len(patient_data)} patient files in '{output_dir}'")


def normalize_surname(s):
    """Normalize surname for comparison."""
    return re.sub(r"\s+", " ", s.strip().upper())


def extract_fragments(text):
    """
    Extract fragments starting with:
    beginning of text OR newline
    followed by surname
    followed by colon
    """
    # The regex looks for lines that start with a surname followed by a colon, capturing the surname and the content
    # that follows until the next match or end of text.
    pattern = re.compile(r'(?:^|\n)\s*([^:\n]+?)\s*:\s*', re.MULTILINE)
    matches = list(pattern.finditer(text))
    fragments = []

    for i, match in enumerate(matches):
        surname = match.group(1).strip()
        start = match.end()
        # Use the start of the next match as the end of the current fragment, or end of text if this is the last match
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        fragments.append((surname, content))

    return fragments


def main():
    parser = argparse.ArgumentParser(description="Split patient texts into separate JSON files.")
    parser.add_argument("inputs", nargs="+", help="Input JSON files")
    parser.add_argument("-o", "--output", required=True, help="Output folder")

    args = parser.parse_args()

    split(args.inputs, args.output)

if __name__ == "__main__":
    main()
