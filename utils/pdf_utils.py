import io
from pathlib import Path
from typing import IO, Any

import boto3
import pdfplumber
from pypdf import PdfReader
from collections import Counter, defaultdict
import statistics
import re

from config import PDF_BUCKET_NAME


def extract_structured_text(
        pdf_path: str | IO[Any] | Path,
        big_font_ratio=1.05,
        small_font_ratio=0.9,
        width_ratio_threshold=0.6,
        centered_tolerance_ratio=0.1,
        signature_distance_threshold=50
):
    """
    Extracts structured text from a PDF by analyzing font sizes, line widths, and layout features to filter out
    non-body content like headers, footers, signatures, and tables.

    :param pdf_path: Path to the PDF file to extract text from.
    :param big_font_ratio: Multiplier to determine the upper bound of body text font size based on the dominant font size.
    :param small_font_ratio: Multiplier to determine the lower bound of body text font size based on the dominant font size.
    :param width_ratio_threshold: Multiplier to determine the minimum line width for body text based on the dominant line width.
    :param centered_tolerance_ratio: Ratio of page width to determine how close to the center a line must be to be considered centered (and thus likely a heading).
    :param signature_distance_threshold: Distance in points from detected signature positions to filter out nearby lines that are likely part of the signature block (e.g., names, titles).
    :return: A string containing the extracted body text from the PDF, with non-body elements filtered out.
    """

    # Detect digital signature rectangles once
    digital_signature_rects = detect_digital_signature_rectangles(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:

        # -------------------------
        # STEP 1: Detect dominant font size
        # -------------------------
        all_sizes = []
        for page in pdf.pages:
            for char in page.chars:
                if char["text"].strip():
                    all_sizes.append(round(char["size"], 1))

        if not all_sizes:
            return ""

        dominant_size = Counter(all_sizes).most_common(1)[0][0]
        min_body_size = dominant_size * small_font_ratio
        max_body_size = dominant_size * big_font_ratio

        # -------------------------
        # STEP 2: Collect lines
        # -------------------------
        all_line_widths = []
        page_lines_all = []

        for page in pdf.pages:
            lines = group_chars_into_lines(page, return_meta=True)
            page_lines_all.append(lines)

            for line in lines:
                if line["width"] > 0:
                    all_line_widths.append(round(line["width"], 1))

        if not all_line_widths:
            return ""

        dominant_width = Counter(all_line_widths).most_common(1)[0][0]
        min_body_width = dominant_width * width_ratio_threshold

        # -------------------------
        # STEP 3: Detect repeated lines
        # -------------------------
        repeated_blocks = Counter()

        for lines in page_lines_all:
            unique_lines = set(l["text"].strip() for l in lines if l["text"].strip())
            for line in unique_lines:
                repeated_blocks[line] += 1

        repetition_threshold = max(2, len(pdf.pages) // 2)

        repeated_lines = {
            line for line, count in repeated_blocks.items()
            if count >= repetition_threshold
        }

        # -------------------------
        # STEP 4: Extract content
        # -------------------------
        page_texts = []

        for page_idx, page in enumerate(pdf.pages):

            lines = page_lines_all[page_idx]
            # Detect column/table-like lines
            column_lines = detect_column_blocks(lines)
            page_body = []
            page_center = page.width / 2

            # -------------------------
            # Detect signature positions
            # -------------------------

            signature_tops = []

            # --- Image-based signatures ---
            image_signatures = detect_signature_images(page)
            for img in image_signatures:
                signature_tops.append(img["top"])

            # --- Digital signatures ---
            for sig_page_idx, rect in digital_signature_rects:
                if sig_page_idx == page_idx:
                    _, y0, _, y1 = rect

                    # Convert bottom-origin (PDF) to top-origin (pdfplumber)
                    digital_top = page.height - y1
                    signature_tops.append(digital_top)

            signature_cut_y = min(signature_tops) if signature_tops else None

            # -------------------------
            # Line filtering
            # -------------------------

            for line_idx, line in enumerate(lines):

                text = line["text"].strip()
                if not text:
                    continue

                line_bottom = line["bottom"]

                # ---- Remove column-structured table blocks ----
                if line_idx in column_lines:
                    continue

                # ---- Signature proximity removal ----
                if signature_cut_y is not None:
                    distance = signature_cut_y - line_bottom

                    if 0 < distance < signature_distance_threshold:
                        # remove short likely name/title lines
                        if len(text.split()) <= 6 and not text.endswith(('.', ';', ':')):
                            continue

                # ---- Repeated headers/footers ----
                if text in repeated_lines:
                    continue

                # ---- Page numbers ----
                if re.fullmatch(r"\s*\d+\s*", text):
                    continue

                # Remove lines starting with Data:
                if text.startswith("Data:"):
                    continue

                # ---- Bold-only headings ----
                if line["is_entirely_bold"]:
                    continue

                # ---- ALL CAPS headings ----
                if text.isupper() and len(text.split()) <= 10:
                    continue

                # ---- Layout filters ----
                avg_size = statistics.mean(line["sizes"])
                width = line["width"]
                min_x = line["min_x"]
                max_x = line["max_x"]

                line_center = (min_x + max_x) / 2
                centered_margin = page.width * centered_tolerance_ratio
                is_centered = abs(line_center - page_center) < centered_margin

                if is_centered and width < min_body_width:
                    continue

                if not (min_body_size <= avg_size <= max_body_size):
                    continue

                if width < min_body_width:
                    continue

                page_body.append(text)

            page_texts.append(merge_lines(page_body))

        return "\n\n".join(page_texts)


def group_chars_into_lines(page, return_meta=False, y_tolerance=2, space_ratio=0.1):
    """Groups characters into lines based on their vertical positions, with a tolerance to account for small misalignments."""
    lines = defaultdict(list)

    for char in page.chars:
        if not char["text"].strip():
            continue
        key = round(char["top"] / y_tolerance) * y_tolerance
        lines[key].append(char)

    sorted_lines = sorted(lines.items(), key=lambda x: x[0])
    result = []

    for _, line_chars in sorted_lines:

        line_chars = sorted(line_chars, key=lambda c: c["x0"])

        reconstructed_line = ""
        sizes = []
        bold_flags = []

        min_x = line_chars[0]["x0"]
        max_x = line_chars[-1]["x1"]
        min_top = min(c["top"] for c in line_chars)
        max_bottom = max(c["bottom"] for c in line_chars)

        for i, char in enumerate(line_chars):

            if i > 0:
                prev = line_chars[i - 1]
                gap = char["x0"] - prev["x1"]
                threshold = prev["size"] * space_ratio

                if gap > threshold:
                    reconstructed_line += " "

            reconstructed_line += char["text"]
            sizes.append(char["size"])
            bold_flags.append("bold" in char["fontname"].lower())

        # Build word boxes
        words = []
        current_word = []
        current_x0 = None

        for i, char in enumerate(line_chars):

            if i > 0:
                prev = line_chars[i - 1]
                gap = char["x0"] - prev["x1"]
                threshold = prev["size"] * space_ratio

                if gap > threshold:
                    # end current word
                    if current_word:
                        words.append({
                            "text": "".join(c["text"] for c in current_word),
                            "x0": current_x0,
                            "x1": prev["x1"]
                        })
                        current_word = []

            if not current_word:
                current_x0 = char["x0"]

            current_word.append(char)

        # finalize last word
        if current_word:
            words.append({
                "text": "".join(c["text"] for c in current_word),
                "x0": current_x0,
                "x1": line_chars[-1]["x1"]
            })

        line_data = {
            "text": reconstructed_line,
            "words": words,
            "sizes": sizes,
            "min_x": min_x,
            "max_x": max_x,
            "width": max_x - min_x,
            "top": min_top,
            "bottom": max_bottom,
            "is_entirely_bold": all(bold_flags)
        }

        result.append(line_data if return_meta else reconstructed_line)

    return result

def detect_signature_images(page, position_bias:bool = False):
    """Detect signature-like images based on size, aspect ratio and position (if position_bias=True)."""
    candidates = []
    if position_bias:
        for img in page.images:
            width = img["x1"] - img["x0"]
            height = img["bottom"] - img["top"]

            if img["top"] > page.height * 0.5:
                if width < page.width * 0.7:
                    aspect_ratio = width / height if height > 0 else 0
                    if 2 < aspect_ratio < 8 and height < 120:
                        candidates.append(img)
    else:
        candidates = page.images

    return candidates

def detect_digital_signature_rectangles(pdf_path: str | IO[Any] | Path):
    reader = PdfReader(pdf_path)
    signature_rects = []

    if "/AcroForm" not in reader.trailer["/Root"]:
        return signature_rects

    form = reader.trailer["/Root"]["/AcroForm"]

    if "/Fields" not in form:
        return signature_rects

    for field in form["/Fields"]:
        field_obj = field.get_object()

        if field_obj.get("/FT") == "/Sig":

            rect = field_obj.get("/Rect")
            page_ref = field_obj.get("/P")

            if rect and page_ref:

                page_obj = page_ref.get_object()

                # Find page index by comparing indirect references
                for i, p in enumerate(reader.pages):
                    if p.indirect_reference == page_obj.indirect_reference:
                        signature_rects.append((i, rect))
                        break

    return signature_rects

def detect_column_blocks(lines, gap_threshold=30, indentation_threshold=30):
    """Detect table-like column blocks using: Large word gaps, Strong indentation, Vertical continuity"""
    candidate_rows = []

    # -------------------------------------------------
    # STEP 1: Detect rows with internal large gaps
    # -------------------------------------------------
    for idx, line in enumerate(lines):

        words = line.get("words", [])
        if len(words) < 2:
            continue

        for i in range(len(words) - 1):
            gap = words[i+1]["x0"] - words[i]["x1"]

            if gap > gap_threshold:
                candidate_rows.append(idx)
                break

    table_indices = set(candidate_rows)

    if not candidate_rows:
        return table_indices

    # -------------------------------------------------
    # STEP 2: Compute table column anchors
    # -------------------------------------------------
    column_x_positions = []

    for idx in candidate_rows:
        words = lines[idx].get("words", [])
        if words:
            column_x_positions.append(words[0]["x0"])

    if not column_x_positions:
        return table_indices

    # Use median as stable column start
    import statistics
    main_column_x = statistics.median(column_x_positions)

    # -------------------------------------------------
    # STEP 3: Add strongly indented lines
    # -------------------------------------------------
    for idx, line in enumerate(lines):

        if idx in table_indices:
            continue

        # Must be inside vertical region of table
        # (between first and last detected row)
        if idx < min(candidate_rows) or idx > max(candidate_rows):
            continue

        words = line.get("words", [])
        if not words:
            continue

        # Strong indentation relative to main column
        indentation = words[0]["x0"] - main_column_x

        if indentation > indentation_threshold:
            table_indices.add(idx)

    return table_indices

def merge_lines(lines):
    """Merge lines into paragraphs based on punctuation and line structure."""
    merged = []
    buffer = ""

    for line in lines:

        if re.match(r"^\d+(\.\d+)*\s+", line):
            if buffer:
                merged.append(buffer.strip())
                buffer = ""
            merged.append(line)
            continue

        if buffer and not buffer.endswith(('.', ';', ':')):
            buffer += " " + line
        else:
            if buffer:
                merged.append(buffer.strip())
            buffer = line

    if buffer:
        merged.append(buffer.strip())

    return "\n".join(merged)

def read_pdf_from_s3(pdf_key:str, bucket_name:str = PDF_BUCKET_NAME) -> io.BytesIO:
    """
    Reads a PDF file from an S3 bucket and returns its content as bytes.
    :param pdf_key: The key (path) of the PDF file in the S3 bucket. (e.g., "documents/test.pdf")
    :param bucket_name: The name of the S3 bucket where the PDF file is stored. Defaults to PDF_BUCKET_NAME from config.
    :return: A BytesIO stream object containing the PDF file's content
    """
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=bucket_name, Key=pdf_key)

    return io.BytesIO(response['Body'].read())

if __name__ == "__main__":
    text = extract_structured_text("erasmus.pdf")
    print(text)