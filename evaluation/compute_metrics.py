import re
from typing import List, Tuple, Dict

from spacy.tokens import Doc


def infer_predicted_spans(original: str, anonymized: str) -> List[Tuple[int, int, str]]:
    """
    Given the original text and an anonymized version with markers [LABEL],
    infer which span of original text each marker replaced.

    Returns list of (start, end, label).
    """

    pattern = r"\[([A-Z]+)\]"
    predicted = []

    while True:
        match = re.search(pattern, anonymized)
        if not match:
            break

        label = match.group(1)
        tag_start, tag_end = match.span()

        # Text BEFORE the tag in anonymized text
        before = anonymized[:tag_start]

        #Take the index of the next entity or the end of the string
        stop_index = anonymized.find('[', tag_end)
        stop_index = stop_index if stop_index != -1 else len(anonymized)
        after = anonymized[tag_end:stop_index]

        end_index = original.find(after, tag_start)
        entity_text = original[tag_start:end_index]

        replaced_start = tag_start
        replaced_end = end_index

        # Record predicted entity
        predicted.append((replaced_start, replaced_end, label))

        anonymized = before + entity_text + anonymized[tag_end:]

    return predicted


def compute_metrics_from_text(inferences: list[dict], labels: list[str],
                              unify_labels: bool = False,
                              log_fp_fn: bool = False) -> Dict[str, Dict[str, float]]:
    """
    Compute micro-averaged precision, recall, and F1 per label on the given list of gold-anonymized inferences.

    inferences: list of dicts
        {
            "gold": { "text": ..., "entities": [(start,end,label), ...] },
            "anonymized": "..."
        }

    labels: iterable of label strings (e.g. ["PER", "LOC", "ORG"])
    """
    gold_docs = [ex["gold"] for ex in inferences]
    pred_entities = [infer_predicted_spans(ex["gold"]["text"], ex["anonymized"]) for ex in inferences]
    pred_docs = [{"text": ex["gold"]["text"], "entities": ents } for ex, ents in zip(inferences, pred_entities)]

    return compute_metrics(gold_docs, pred_docs, labels, unify_labels, log_fp_fn)

def compute_metrics_from_spacy_docs(gold_docs: list[dict], pred_docs: list[Doc], labels: list[str],
                                    log_fp_fn: bool = False) -> Dict[str, Dict[str, float]]:
    """
    Compute per-label and micro-averaged precision/recall/F1 using spaCy Doc objects.
    :param gold_docs: -- ground truth in the form { "text": ..., "entities": [(start,end,label), ...] },
    :param pred_docs: -- model predictions in the form of spaCy Doc objects
    :param labels: -- entity labels to score
    :param recognize_more_tp: -- if True, matches that include the whole gold span are considered both
                            true positives and false positives
    :param unify_labels: -- if True, an additional label "ENT" is used for scoring all entities together
    :param log_fp_fn: -- if True, save false positives and false negatives to text files for analysis
    :return: dict of metrics per label
    """
    pred_docs = [
        {
            "text": pred_doc.text,
            "entities": {(ent.start_char, ent.end_char, ent.label_) for ent in pred_doc.ents}
        }
        for pred_doc in pred_docs
    ]

    return compute_metrics(gold_docs, pred_docs, labels, log_fp_fn)


def _save_fp_fn(gold_lbl: set[tuple[int, int, str]], pred_lbl: set[tuple[int, int, str]], text: str):
    """Save false positives and false negatives to text files for analysis."""
    false_positives = [(text[s:e], l) for (s, e, l) in pred_lbl - gold_lbl]
    false_negatives = [(text[s:e], l) for (s, e, l) in gold_lbl - pred_lbl]

    # Save to a text file
    with open("fp.txt", "a", encoding="utf-8") as f:
        for text, label in false_positives:
            f.write(f"{label}\t{text}\n")

    with open("fn.txt", "a", encoding="utf-8") as f:
        for text, label in false_negatives:
            f.write(f"{label}\t{text}\n")


def _get_metrics_dictionary(gold_docs: list[dict],
                            pred_docs: list[dict],
                            labels: list[str],
                            log_fp_fn: bool = False) -> Dict[str, Dict[str, float]]:
    # Initialize counters
    label_counts = {lbl: {"tp": 0, "fp": 0, "fn": 0, "gold": 0, "tp_p": 0} for lbl in labels}
    total_tp = total_fp = total_fn = total_gold = total_tp_p = 0

    for gold_doc, pred_doc in zip(gold_docs, pred_docs):

        gold_entities = {(ent[0], ent[1], ent[2]) for ent in gold_doc["entities"]}
        pred_entities = {(ent[0], ent[1], ent[2]) for ent in pred_doc["entities"]}

        for lbl in labels:
            gold_lbl = {(s, e, l) for (s, e, l) in gold_entities if l == lbl}
            pred_lbl = {(s, e, l) for (s, e, l) in pred_entities if l == lbl}
            fully_covered_lbl = {g for g in gold_lbl for p in pred_lbl if p[0] <= g[0] and p[1] >= g[1]}

            tp_p = len(fully_covered_lbl)
            tp = len(gold_lbl & pred_lbl)
            fp = len(pred_lbl - gold_lbl)
            fn = len(gold_lbl - pred_lbl)

            if log_fp_fn: _save_fp_fn(gold_lbl, pred_lbl, gold_doc['text'])

            label_counts[lbl]["tp"] += tp
            label_counts[lbl]["fp"] += fp
            label_counts[lbl]["fn"] += fn
            label_counts[lbl]["gold"] += len(gold_lbl)
            label_counts[lbl]["tp_p"] += tp_p

            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_gold += len(gold_lbl)
            total_tp_p += tp_p

    # Compute final metrics
    results = {}

    for lbl in labels:
        tp = label_counts[lbl]["tp"]
        fp = label_counts[lbl]["fp"]
        fn = label_counts[lbl]["fn"]
        gold = label_counts[lbl]["gold"]
        tp_p = label_counts[lbl]["tp_p"]

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        coverage = tp_p / gold if gold else 0.0

        results[lbl] = {
            "precision": precision,
            "recall": recall,
            "coverage": coverage,
            "f1": f1
        }

    # Compute macro and micro averages
    micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
    micro_f = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) else 0.0
    micro_c = total_tp_p / total_gold if total_gold else 0.0
    results["macro"] = {
        "precision": sum(results[lbl]["precision"] for lbl in labels) / len(labels) if labels else 0.0,
        "recall": sum(results[lbl]["recall"] for lbl in labels) / len(labels) if labels else 0.0,
        "f1": sum(results[lbl]["f1"] for lbl in labels) / len(labels) if labels else 0.0,
        "coverage": sum(results[lbl]["coverage"] for lbl in labels) / len(labels) if labels else 0.0
    }
    results["weighted"] = {
        "precision": sum(label_counts[lbl]["gold"] / total_gold * results[lbl]["precision"] for lbl in
                         labels) if total_gold else 0.0,
        "recall": sum(
            label_counts[lbl]["gold"] / total_gold * results[lbl]["recall"] for lbl in labels) if total_gold else 0.0,
        "f1": sum(label_counts[lbl]["gold"] / total_gold * results[lbl]["f1"] for lbl in labels) if total_gold else 0.0,
        "coverage": sum(label_counts[lbl]["gold"] / total_gold * results[lbl]["coverage"] for lbl in labels) if total_gold else 0.0
    }
    results["micro"] = {"precision": micro_p, "recall": micro_r, "f1": micro_f, "coverage": micro_c}

    return results


def compute_metrics(gold_docs: list[dict],
                    pred_docs: list[dict],
                    labels: list[str],
                    log_fp_fn: bool = False) -> Dict[str, Dict[str, float]]:
    """
    Compute per-label and micro-averaged precision/recall/F1 using spaCy Doc objects.

    :param gold_docs: list[dict]   -- ground truth in the form { "text": ..., "entities": [(start,end,label), ...] },
    :param pred_docs: list[dict]   -- model predictions in the form of spaCy Doc objects
    :param labels: list[str]       -- entity labels to score
    :param log_fp_fn: bool         -- if True, save false positives and false negatives to text files for analysis
    :return: dict of metrics per label
    """
    gold_docs_ent = []
    pred_docs_ent = []
    present_labels = set()

    # Create unified label versions and track present labels
    for doc in gold_docs:
        new_entities = []
        for (s, e, l) in doc["entities"]:
            if l in labels:
                new_entities.append((s, e, "ENT"))
                present_labels.add(l)
        gold_docs_ent.append({"text": doc["text"], "entities": new_entities})

    # Create unified label versions for predictions
    for doc in pred_docs:
        new_entities = [(s, e, "ENT") for (s, e, l) in doc["entities"] if l in labels]
        pred_docs_ent.append({"text": doc["text"], "entities": new_entities})

    labels_dict = _get_metrics_dictionary(gold_docs, pred_docs, sorted(list(present_labels)), log_fp_fn)
    labels_ent_dict = _get_metrics_dictionary(gold_docs_ent, pred_docs_ent, ["ENT"], log_fp_fn)
    return {
        **labels_dict,
        "ENT": labels_ent_dict["ENT"]
    }