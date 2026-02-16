#!/usr/bin/env python3

import os
import warnings
import argparse
import sys
import json
import spacy
import spacy_transformers

from anonymization_functions import anonymize_texts
from config import DEFAULT_NER_MODEL, PERSONAL_DATA_FORMAT, DEFAULT_OUTPUTS_IN_SINGLE_FILE
from utils import read_json_file
from utils.anonymization_utils import save_anonymized_text, read_file, save_many_texts, save_metrics
from GUI.GUI import main as gui_main

import multiprocessing as mp
mp.freeze_support()
mp.set_start_method("spawn", force=True)

warnings.filterwarnings("ignore", message=r".*\[W095\].*")


# ----------------------------
#   Anonymization Lambda
# ----------------------------
def anonimize(inputs: list[str],
              output_dir: str = None,
              text: str = None,
              entities: list[str] = None,
              per_matching: int = None,
              personal_data: str = None) -> str:
    """
    Anonymizes text using spaCy NER and additional rules, with flexible input and output options.

    :param inputs: list of input file and/or folder paths. Each file can be a .txt, .json, or .docx file. If a folder is provided, all files in the folder will be processed. In case of JSON files, each of these can also contain a dictionary of personal data.
    :param output_dir: folder path where to save anonymized text. If omitted and input is a file, output will be saved in the same folder as the input file. If omitted and input is raw text, anonymized text will be printed to stdout.
    :param text: raw text to anonymize. If provided, this takes precedence over file inputs.
    :param entities: list of entity types to anonymize. If omitted, default entity types will be used.
    :param per_matching: whether to anonymize PER and PATIENT entities in combination with dictionaries or not. If omitted, the default level of extra matching will be applied.
    :param personal_data: path to json dictionary of specific personal data to anonymize.
    :return: the path to the saved anonymized file directory.
    """

    #  Retrieve input text
    texts = []
    metadata = []
    personal_data_list = []

    # INPUT CASE 1: direct text input via --text
    if text:
        texts = [text]
        metadata = [None]
        personal_data_list = [None]

    # INPUT CASE 2: Files / Folders
    elif inputs:
        expanded_files = []

        for path in inputs:
            if os.path.isdir(path):
                for filename in os.listdir(path):
                    full_path = os.path.join(path, filename)
                    if os.path.isfile(full_path):
                        expanded_files.append(full_path)
            elif os.path.isfile(path):
                expanded_files.append(path)
            else:
                print(f"Warning: '{path}' is not valid.", file=sys.stderr)

        if not expanded_files:
            print("Error: No valid input files found.", file=sys.stderr)
            sys.exit(1)

        for filepath in expanded_files:
            try:
                t, m, pd = read_file(filepath)
                texts.extend(t)
                metadata.extend(m if m else [None] * len(t))
                personal_data_list.extend([pd] * len(t))
            except Exception as e:
                print(f"Error reading '{filepath}': {e}", file=sys.stderr)
                sys.exit(1)

    # CASE 3: stdin fallback
    elif not sys.stdin.isatty():
        texts = [sys.stdin.read().strip()]
        metadata = [None]
        personal_data_list = [None]

    if not texts:
        print("Error: Provide text or at least one input file/folder.", file=sys.stderr)
        sys.exit(1)

    if personal_data:
        try:
            pd = read_json_file(personal_data)
            personal_data_list = [pd] * len(texts)
        except Exception as e:
            print(f"Error reading personal data file '{personal_data}': {e}", file=sys.stderr)
            sys.exit(1)

    if per_matching is not None:
        if per_matching not in [0, 1, 2]:
            print("Error: per_matching must be 0, 1, or 2.", file=sys.stderr)
            sys.exit(1)
        per_matching = per_matching

    # Load spaCy model
    try:
        nlp = spacy.load(DEFAULT_NER_MODEL)
    except Exception as e:
        print(f"Error loading spaCy model: {e}", file=sys.stderr)
        sys.exit(1)

    # Anonymize
    anonymized, metrics = anonymize_texts(texts,
                                          nlp=nlp,
                                          entities=entities,
                                          per_matching=per_matching,
                                          personal_data=personal_data_list,
                                          meta_data=metadata)
    # Output result
    out_path = None
    if output_dir:
        if not os.path.isdir(output_dir):
            print(f"Provided folder path '{output_dir}' is not a valid directory.", file=sys.stderr)
            sys.exit(1)
        out_dir = output_dir
    elif inputs:
        if len(inputs) == 1:
            out_dir = os.path.dirname(inputs[0]) if os.path.isfile(inputs[0]) else inputs[0]
        else:
            print("Multiple input files provided without output_dir. Please specify an output directory.", file=sys.stderr)
            sys.exit(1)
    else:
        print(anonymized)
        return None

    try:
        out_path = save_many_texts(anonymized,
                                   output_dir=out_dir,
                                   single_file=DEFAULT_OUTPUTS_IN_SINGLE_FILE,
                                   metadata=metadata,
                                   personal_data=personal_data_list)
    except Exception as e:
        print(f"Error writing to directory '{out_dir}': {e}", file=sys.stderr)
        sys.exit(1)

    if out_path:
        print(f"Anonymized text saved to '{out_path}'.")
        if metrics:
            save_metrics(metrics, output_dir=os.path.dirname(out_path), original_filename=os.path.basename(out_path))

    return out_path

# ----------------------------
#   CLI logic
# ----------------------------
def main():
    parser = argparse.ArgumentParser(description="Anonymize text based on spaCy NER and additional rules.")

    # Command options
    parser.add_argument("inputs", nargs="*", help="Input files and/or folders containing files to anonymize. In case of JSON files, each of these can also contain a dictionary of personal data.")
    parser.add_argument("--output-dir", type=str, help="Folder path where to save anonymized text. If omitted and input is a file, output will be saved in the same folder as the input file. If omitted and input is raw text, anonymized text will be printed to stdout.")
    parser.add_argument("--text", type=str, help="Raw text to anonymize.")
    parser.add_argument("--entities", type=str, nargs="+", help="List of entity types to anonymize.")
    parser.add_argument("--per-matching", type=int, help="Enable extra matching for PER and PATIENT entities using dictionaries with increasing level of strictness: 0 = no extra matching, 1 = match only dictionary-unambiguous names, 2 = match all names.")
    parser.add_argument("--personal-data", type=str, help=f"Path to json dictionary of specific personal data to anonymize. Provided dictionary should have the following fields: {list(PERSONAL_DATA_FORMAT.keys())}.")
    parser.add_argument("--gui", action="store_true", help="Launch the graphical user interface.")

    args = parser.parse_args()

    # -----------------------------------
    # GUI MODE
    # -----------------------------------
    if args.gui or len(sys.argv) == 1:
        gui_main()
        return

    # -----------------------------------
    # CLI MODE
    # -----------------------------------
    anonimize(inputs=args.inputs,
              output_dir=args.output_dir,
              text=args.text,
              entities=args.entities,
              per_matching=args.per_matching,
              personal_data=args.personal_data)


if __name__ == "__main__":
    main()