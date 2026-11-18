
import re

from .profile_extractor import (
    match_section_heading,
    is_document_boundary,
)


# ---------------------------------------------------------
# CHUNKING CONFIGURATION
# ---------------------------------------------------------

DEFAULT_MAX_CHARS = 1200
DEFAULT_OVERLAP_CHARS = 150

BULLET_PATTERN = re.compile(
    r"^(?:[•●▪◦‣]|[-*]\s+|\d+[.)]\s+|"
    r"[a-zA-Z][.)]\s+|[ivxlcdmIVXLCDM]+[.)]\s+)"
)

CHAPTER_PATTERN = re.compile(
    r"^chapter\s+(?:[ivxlcdm]+|\d+)"
    r"(?:\s*[:.\-–—].*)?$",
    re.IGNORECASE
)


# ---------------------------------------------------------
# TEXT CLEANING
# ---------------------------------------------------------

def normalize_line(text):
    """Remove invisible characters and normalize whitespace."""

    text = str(text)

    text = text.replace("\u00a0", " ")
    text = text.replace("\u00ad", "")
    text = text.replace("\u200b", "")

    return re.sub(r"[ \t]+", " ", text).strip()


def join_wrapped_lines(lines):
    """Join lines belonging to the same paragraph."""

    result = ""

    for line in lines:

        line = normalize_line(line)

        if not line:
            continue

        if not result:
            result = line
            continue

        if result.endswith("-") and line[0].islower():
            result = result[:-1] + line
        else:
            result += " " + line

    return result.strip()


def get_page_text(page):
    """Select the best available original page text."""

    if page.get("extraction_method") == "ocr":

        candidates = [
            page.get("ocr_text"),
            page.get("text"),
            page.get("raw_text"),
        ]

    else:

        candidates = [
            page.get("raw_text"),
            page.get("text"),
            page.get("ocr_text"),
        ]

    for candidate in candidates:

        if isinstance(candidate, str) and candidate.strip():
            return candidate

    return ""


# ---------------------------------------------------------
# PARAGRAPH EXTRACTION
# ---------------------------------------------------------

def extract_paragraphs(pages):
    """Extract paragraphs while preserving sections and pages."""

    paragraphs = []

    current_section = None
    paragraph_lines = []
    paragraph_id = 1

    def save_paragraph(page_number):

        nonlocal paragraph_id

        if not paragraph_lines:
            return

        text = join_wrapped_lines(paragraph_lines)

        if text:

            paragraphs.append({
                "paragraph_id": paragraph_id,
                "section": current_section,
                "page_number": page_number,
                "text": text,
                "character_count": len(text),
            })

            paragraph_id += 1

        paragraph_lines.clear()

    for page_index, page in enumerate(pages, start=1):

        page_number = page.get("page_number", page_index)
        page_text = get_page_text(page)

        if not page_text:
            continue

        for raw_line in page_text.splitlines():

            line = normalize_line(raw_line)

            if not line:
                save_paragraph(page_number)
                continue

            # Detect research section headings.
            detected_section, remaining_text = (
                match_section_heading(line)
            )

            if detected_section:

                save_paragraph(page_number)

                current_section = detected_section

                if remaining_text:
                    paragraph_lines.append(remaining_text)

                continue

            # Stop collecting text at document boundaries.
            if (
                is_document_boundary(line)
                or CHAPTER_PATTERN.fullmatch(line)
            ):

                save_paragraph(page_number)
                current_section = None
                continue

            # Keep bullet points and numbered items separate.
            if BULLET_PATTERN.match(line):
                save_paragraph(page_number)

            paragraph_lines.append(line)

        # Preserve page boundaries.
        save_paragraph(page_number)

    return paragraphs


# ---------------------------------------------------------
# SPLIT LONG PARAGRAPHS
# ---------------------------------------------------------

def split_long_sentence(sentence, max_chars):
    """Split unusually long sentences by words."""

    words = sentence.split()

    pieces = []
    current_piece = ""

    for word in words:

        if len(word) > max_chars:

            if current_piece:
                pieces.append(current_piece)
                current_piece = ""

            for start in range(0, len(word), max_chars):
                pieces.append(word[start:start + max_chars])

            continue

        candidate = f"{current_piece} {word}".strip()

        if len(candidate) <= max_chars:
            current_piece = candidate

        else:

            if current_piece:
                pieces.append(current_piece)

            current_piece = word

    if current_piece:
        pieces.append(current_piece)

    return pieces


def split_long_paragraph(paragraph, max_chars):
    """Split long paragraphs into manageable sentence-aware segments."""

    text = paragraph["text"]

    if len(text) <= max_chars:
        return [paragraph.copy()]

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    segments = []
    current_segment = ""

    for sentence in sentences:

        sentence = sentence.strip()

        if not sentence:
            continue

        if len(sentence) > max_chars:

            if current_segment:
                segments.append(current_segment)
                current_segment = ""

            segments.extend(
                split_long_sentence(sentence, max_chars)
            )

            continue

        candidate = f"{current_segment} {sentence}".strip()

        if len(candidate) <= max_chars:
            current_segment = candidate

        else:

            if current_segment:
                segments.append(current_segment)

            current_segment = sentence

    if current_segment:
        segments.append(current_segment)

    result = []

    for segment in segments:

        result.append({
            **paragraph,
            "text": segment,
            "character_count": len(segment),
        })

    return result


# ---------------------------------------------------------
# CHUNK GENERATION
# ---------------------------------------------------------

def calculate_chunk_length(units):
    """Calculate chunk length, including paragraph separators."""

    if not units:
        return 0

    return sum(
        len(unit["text"])
        for unit in units
    ) + (len(units) - 1) * 2


def select_overlap_units(units, overlap_chars):
    """
    Select trailing context from the previous chunk.

    Unlike the original implementation, this can retain
    part of a long paragraph instead of requiring the
    entire paragraph to fit within the overlap limit.
    """

    selected_reversed = []
    used_chars = 0

    for unit in reversed(units):

        separator_length = 2 if selected_reversed else 0

        available_chars = (
            overlap_chars
            - used_chars
            - separator_length
        )

        if available_chars <= 0:
            break

        text = unit["text"]

        if len(text) <= available_chars:

            selected_reversed.append({
                **unit,
                "_overlap": True,
            })

            used_chars += len(text) + separator_length

        else:

            # Keep only the ending of a long paragraph.
            tail = text[-available_chars:]

            # Avoid starting halfway through a word.
            first_space = tail.find(" ")

            if first_space != -1:
                tail = tail[first_space + 1:]

            tail = tail.strip()

            if tail:

                selected_reversed.append({
                    **unit,
                    "text": tail,
                    "character_count": len(tail),
                    "_overlap": True,
                })

            break

    return list(reversed(selected_reversed))


def build_chunk_record(units, chunk_number):
    """Create a structured chunk with source references."""

    pages = sorted({
        unit["page_number"]
        for unit in units
    })

    text = "\n\n".join(
        unit["text"]
        for unit in units
    )

    paragraph_ids = {
        unit["paragraph_id"]
        for unit in units
    }

    overlap_characters = sum(
        len(unit["text"])
        for unit in units
        if unit.get("_overlap")
    )

    return {
        "chunk_id": f"chunk-{chunk_number:04d}",
        "section": units[0]["section"],
        "pages": pages,
        "page_start": min(pages),
        "page_end": max(pages),
        "paragraph_count": len(paragraph_ids),
        "character_count": len(text),
        "overlap_characters": overlap_characters,
        "text": text,
    }


def chunk_paragraphs(
    paragraphs,
    max_chars=DEFAULT_MAX_CHARS,
    overlap_chars=DEFAULT_OVERLAP_CHARS,
):
    """
    Create paragraph-aware chunks.

    Chunks never cross research section boundaries.
    Overlap is taken from the trailing content of the
    previous chunk.
    """

    if max_chars <= 0:
        raise ValueError(
            "max_chars must be greater than zero."
        )

    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError(
            "overlap_chars must be at least zero "
            "and smaller than max_chars."
        )

    units = []

    for paragraph in paragraphs:

        units.extend(
            split_long_paragraph(
                paragraph,
                max_chars
            )
        )

    chunks = []
    current_units = []

    def save_chunk():

        if current_units:

            chunks.append(
                build_chunk_record(
                    current_units,
                    len(chunks) + 1
                )
            )

    for unit in units:

        # Never combine different research sections.
        if (
            current_units
            and unit["section"] != current_units[0]["section"]
        ):

            save_chunk()
            current_units = []

        candidate_units = current_units + [unit]

        if (
            current_units
            and calculate_chunk_length(candidate_units) > max_chars
        ):

            save_chunk()

            # Retain trailing context from the previous chunk.
            current_units = select_overlap_units(
                current_units,
                overlap_chars
            )

            # Ensure the overlap plus new content fits.
            while (
                current_units
                and calculate_chunk_length(
                    current_units + [unit]
                ) > max_chars
            ):

                current_units.pop(0)

        current_units.append(unit)

    save_chunk()

    return chunks


# ---------------------------------------------------------
# MAIN PROCESSING FUNCTION
# ---------------------------------------------------------

def process_pdf_extraction(
    pdf_data,
    max_chars=DEFAULT_MAX_CHARS,
    overlap_chars=DEFAULT_OVERLAP_CHARS,
):
    """Convert a Phase 2 PDF extraction into research chunks."""

    if not isinstance(pdf_data, dict):
        raise TypeError(
            "PDF extraction result must be a dictionary."
        )

    pages = pdf_data.get("pages")

    if not isinstance(pages, list):
        raise ValueError(
            "PDF extraction result must contain a pages list."
        )

    paragraphs = extract_paragraphs(pages)

    chunks = chunk_paragraphs(
        paragraphs,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
    )

    return {
        "source_type": "research_chunks",
        "source_file": pdf_data.get("file_name"),
        "page_count": pdf_data.get("page_count", len(pages)),

        "processing_config": {
            "max_chars": max_chars,
            "overlap_chars": overlap_chars,
        },

        "total_paragraphs": len(paragraphs),
        "total_chunks": len(chunks),
        "chunks": chunks,
    }
