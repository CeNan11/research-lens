
from pathlib import Path
import re

import pymupdf
import pytesseract
from PIL import Image


# Pages with fewer characters than this may need OCR.
OCR_TEXT_THRESHOLD = 80

# OCR rendering resolution.
OCR_DPI = 300


def normalize_text(text):
    """Normalize whitespace in extracted text."""
    return re.sub(r"\s+", " ", text).strip()


def clean_page_text(raw_text):
    """Clean PDF text while preserving paragraph breaks."""

    text = raw_text.replace("\u00a0", " ")
    text = text.replace("\u00ad", "")
    text = text.replace("\u200b", "")

    lines = text.splitlines()

    paragraphs = []
    current_paragraph = []

    for line in lines:
        line = re.sub(r"[ \t]+", " ", line).strip()

        if not line:
            if current_paragraph:
                paragraphs.append(" ".join(current_paragraph))
                current_paragraph = []
            continue

        # Reconnect words split by PDF line wrapping.
        if (
            current_paragraph
            and current_paragraph[-1].endswith("-")
            and line[0].islower()
        ):
            current_paragraph[-1] = (
                current_paragraph[-1][:-1] + line
            )
        else:
            current_paragraph.append(line)

    if current_paragraph:
        paragraphs.append(" ".join(current_paragraph))

    return "\n\n".join(paragraphs)


def extract_ocr_text(page):
    """Render a PDF page and extract text using Tesseract."""

    pixmap = page.get_pixmap(
        dpi=OCR_DPI,
        colorspace=pymupdf.csRGB,
        alpha=False
    )

    image = Image.frombytes(
        "RGB",
        (pixmap.width, pixmap.height),
        pixmap.samples
    )

    return pytesseract.image_to_string(
        image,
        lang="eng",
        config="--psm 3"
    )


# ------------------------------------------------------------------
# TITLE EXTRACTION
# ------------------------------------------------------------------

def extract_title_from_native_page(page):
    """
    Identify a likely title using font sizes and positions
    from the first page's selectable text.
    """

    page_data = page.get_text("dict", sort=True)
    page_height = page.rect.height

    candidate_lines = []

    ignored_headings = (
        "abstract",
        "keywords",
        "table of contents"
    )

    ignored_prefixes = (
        "republic of the philippines",
        "university of",
        "college of",
        "department of",
        "school of",
        "institute of"
    )

    for block in page_data.get("blocks", []):

        for line in block.get("lines", []):

            spans = [
                span
                for span in line.get("spans", [])
                if span.get("text", "").strip()
            ]

            if not spans:
                continue

            text = "".join(
                span.get("text", "")
                for span in spans
            )

            text = normalize_text(text)

            if not text:
                continue

            lower_text = text.casefold()

            if lower_text in ignored_headings:
                continue

            if lower_text.startswith(ignored_prefixes):
                continue

            # Only consider text in the upper half of the page.
            y0 = min(span["bbox"][1] for span in spans)
            y1 = max(span["bbox"][3] for span in spans)

            if y0 > page_height * 0.50:
                continue

            # Ignore short lines such as page numbers.
            meaningful_characters = re.sub(
                r"[^A-Za-zÀ-ÖØ-öø-ÿ0-9]",
                "",
                text
            )

            if len(meaningful_characters) < 5:
                continue

            font_size = max(
                float(span.get("size") or 0)
                for span in spans
            )

            if font_size <= 0:
                continue

            candidate_lines.append({
                "text": text,
                "y0": y0,
                "y1": y1,
                "height": y1 - y0,
                "font_size": font_size
            })

    if not candidate_lines:
        return None

    candidate_lines.sort(key=lambda item: item["y0"])

    # The largest text near the top of the page is a likely title.
    largest_font = max(
        item["font_size"]
        for item in candidate_lines
    )

    minimum_font = largest_font * 0.78

    large_lines = [
        item
        for item in candidate_lines
        if item["font_size"] >= minimum_font
    ]

    if not large_lines:
        return None

    # Keep the first nearby group of large text lines.
    # This helps avoid accidentally including a separate heading.
    selected_lines = [large_lines[0]]

    for line in large_lines[1:]:
        previous = selected_lines[-1]

        vertical_gap = line["y0"] - previous["y1"]
        maximum_gap = max(
            12,
            previous["height"] * 1.1
        )

        if vertical_gap > maximum_gap:
            break

        selected_lines.append(line)

    title = " ".join(
        item["text"]
        for item in selected_lines
    )

    title = normalize_text(title)

    return title if len(title) >= 6 else None


def is_title_boundary(line):
    """Check whether an OCR line likely marks the end of the title."""

    lower_line = line.casefold()

    boundary_phrases = (
        "presented to",
        "submitted to",
        "in partial fulfillment",
        "in partial fulfilment",
        "requirements for",
        "research title proposal",
        "thesis proposal",
        "research proposal",
        "dissertation proposal",
        "capstone proposal"
    )

    if any(
        phrase in lower_line
        for phrase in boundary_phrases
    ):
        return True

    # Stop when a publication or submission date is encountered.
    if re.search(
        r"\b(?:January|February|March|April|May|June|July|"
        r"August|September|October|November|December)\s+"
        r"\d{1,2},?\s+\d{4}\b",
        line,
        re.IGNORECASE
    ):
        return True

    # Stop when an author name in surname-first format appears.
    if re.match(
        r"^[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]+,\s*"
        r"[A-ZÀ-ÖØ-Þ]",
        line
    ):
        return True

    return False


def extract_title_from_ocr_text(ocr_text):
    """
    Estimate the title from OCR lines when the PDF has no
    selectable text on its cover page.
    """

    if not ocr_text:
        return None

    lines = [
        normalize_text(line)
        for line in ocr_text.splitlines()
        if normalize_text(line)
    ]

    # Remove common institutional headers before the title.
    header_prefixes = (
        "republic of the philippines",
        "university of",
        "college of",
        "department of",
        "school of",
        "institute of"
    )

    while lines and lines[0].casefold().startswith(header_prefixes):
        lines.pop(0)

    candidate_lines = []

    for line in lines:

        if is_title_boundary(line):
            break

        # An institution name after the title usually belongs
        # to the presentation or submission information.
        lower_line = line.casefold()

        if candidate_lines and lower_line.startswith(header_prefixes):
            break

        candidate_lines.append(line)

        # Avoid accidentally collecting author names or other
        # cover-page information as part of the title.
        if len(candidate_lines) >= 4:
            break

    if not candidate_lines:
        return None

    # Reconnect words split by OCR line wrapping.
    title_lines = []

    for line in candidate_lines:

        if (
            title_lines
            and title_lines[-1].endswith("-")
            and line[0].islower()
        ):
            title_lines[-1] = (
                title_lines[-1][:-1] + line
            )
        else:
            title_lines.append(line)

    title = " ".join(title_lines)
    title = normalize_text(title)

    return title if len(title) >= 6 else None


def extract_cover_title(page, fallback_text=None):
    """Extract the title from native PDF text or OCR text."""

    title = extract_title_from_native_page(page)

    if title:
        return title

    if fallback_text:
        return extract_title_from_ocr_text(fallback_text)

    return None


# ------------------------------------------------------------------
# AUTHOR EXTRACTION
# ------------------------------------------------------------------

def extract_author_lines(lines):
    """Identify multiple surname-first author names."""

    full_text = " ".join(lines)
    full_text = normalize_text(full_text)

    # Find the section after the academic fulfillment statement.
    anchor_match = re.search(
        r"in\s+partial\s+fulfillment",
        full_text,
        re.IGNORECASE
    )

    if anchor_match:
        candidate_text = full_text[anchor_match.end():]

    else:
        excluded_terms = (
            "university",
            "college",
            "department",
            "school",
            "philippines",
            "davao",
            "city",
            "barangay",
            "bo.",
            "street",
            "road",
            "avenue",
            "campus",
            "institute"
        )

        filtered_lines = [
            line
            for line in lines
            if not any(
                term in line.casefold()
                for term in excluded_terms
            )
        ]

        candidate_text = " ".join(filtered_lines)

    # Stop before a publication date.
    date_match = re.search(
        r"\b(?:January|February|March|April|May|June|July|"
        r"August|September|October|November|December)\s+"
        r"\d{1,2},?\s+\d{4}\b",
        candidate_text,
        re.IGNORECASE
    )

    if date_match:
        candidate_text = candidate_text[:date_match.start()]

    # Find possible surname markers, such as "Delgado," or "Labay,".
    surname_pattern = re.compile(
        r"(?<!\w)([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]+),\s*"
    )

    # Validate names in surname-first format.
    author_pattern = re.compile(
        r"^[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]+,\s*"
        r"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*\.?"
        r"(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*\.?){0,4}$"
    )

    surname_matches = list(
        surname_pattern.finditer(candidate_text)
    )

    authors = []
    seen = set()

    for index, match in enumerate(surname_matches):

        start = match.start()

        if index + 1 < len(surname_matches):
            end = surname_matches[index + 1].start()
        else:
            end = len(candidate_text)

        candidate = normalize_text(
            candidate_text[start:end]
        ).strip(" ,;")

        if author_pattern.fullmatch(candidate):

            if candidate.casefold() not in seen:
                authors.append(candidate)
                seen.add(candidate.casefold())

    return authors


def extract_cover_authors(page, fallback_text=None):
    """Extract authors from native PDF text or OCR text."""

    lines = []

    blocks = page.get_text("blocks", sort=True)

    for block in blocks:

        for raw_line in block[4].splitlines():

            line = raw_line.replace("\u200b", "")
            line = normalize_text(line)

            if line:
                lines.append(line)

    authors = extract_author_lines(lines)

    # Use OCR text if native PDF extraction found no authors.
    if not authors and fallback_text:

        fallback_lines = [
            normalize_text(line)
            for line in fallback_text.splitlines()
            if line.strip()
        ]

        authors = extract_author_lines(fallback_lines)

    return authors


# ------------------------------------------------------------------
# MAIN PDF EXTRACTION
# ------------------------------------------------------------------

def extract_pdf(pdf_path):
    """Extract PDF metadata and page-by-page text with OCR fallback."""

    pdf_file = Path(pdf_path).expanduser()

    if not pdf_file.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_file}"
        )

    if not pdf_file.is_file():
        raise ValueError(
            "The supplied path is not a file."
        )

    if pdf_file.suffix.lower() != ".pdf":
        raise ValueError(
            "The supplied file must be a PDF."
        )

    try:
        with pymupdf.open(str(pdf_file)) as document:

            if document.needs_pass:
                raise ValueError(
                    "This PDF is password-protected."
                )

            pages = []

            for page_number, page in enumerate(document, start=1):

                # First attempt: extract selectable text.
                native_text = page.get_text(
                    "text",
                    sort=True
                ).strip()

                # Check whether the page contains embedded images.
                has_images = bool(
                    page.get_images(full=True)
                )

                ocr_attempted = False
                ocr_text = ""

                final_text = native_text

                extraction_method = (
                    "text" if native_text else "none"
                )

                # Second attempt: OCR when the page is image-based
                # and contains very little selectable text.
                if (
                    len(native_text) < OCR_TEXT_THRESHOLD
                    and has_images
                ):
                    ocr_attempted = True

                    ocr_text = extract_ocr_text(page).strip()

                    # Prefer OCR if it produces more text.
                    if len(ocr_text) > len(native_text):
                        final_text = ocr_text
                        extraction_method = "ocr"

                cleaned_text = clean_page_text(final_text)

                pages.append({
                    "page_number": page_number,
                    "raw_text": native_text,
                    "ocr_text": ocr_text,
                    "text": cleaned_text,
                    "has_images": has_images,
                    "ocr_attempted": ocr_attempted,
                    "extraction_method": extraction_method,
                    "character_count": len(cleaned_text)
                })

            # Combine pages while preserving page references.
            full_text = "\n\n".join(
                f"[Page {page['page_number']}]\n{page['text']}"
                for page in pages
                if page["text"]
            )

            pdf_metadata = document.metadata or {}

            pages_with_text = sum(
                1 for page in pages if page["text"]
            )

            pages_ocr = sum(
                1 for page in pages
                if page["extraction_method"] == "ocr"
            )

            pages_without_text = sum(
                1 for page in pages if not page["text"]
            )

            # Keep the original OCR text for metadata fallback.
            first_page_ocr = (
                pages[0]["ocr_text"]
                if pages
                else None
            )

            # Extract title and authors from the cover page.
            cover_title = (
                extract_cover_title(
                    document[0],
                    fallback_text=first_page_ocr
                )
                if document.page_count
                else None
            )

            authors = (
                extract_cover_authors(
                    document[0],
                    fallback_text=first_page_ocr
                )
                if document.page_count
                else []
            )

            # Preserve embedded PDF metadata as a fallback.
            embedded_title = (
                pdf_metadata.get("title") or ""
            ).strip() or None

            embedded_author = (
                pdf_metadata.get("author") or ""
            ).strip() or None

            # Prefer the title detected on the cover page.
            final_title = cover_title or embedded_title

            if not authors and embedded_author:
                authors = [embedded_author]

            title_extraction_method = (
                "cover_page"
                if cover_title
                else "pdf_metadata"
                if embedded_title
                else None
            )

            return {
                "source_type": "pdf",
                "file_name": pdf_file.name,

                "metadata": {
                    "title": final_title,
                    "title_extraction_method": title_extraction_method,
                    "pdf_title_metadata": embedded_title,
                    "authors": authors,
                    "pdf_author_metadata": embedded_author,
                    "subject": pdf_metadata.get("subject") or None,
                    "keywords": pdf_metadata.get("keywords") or None,
                    "creator": pdf_metadata.get("creator") or None,
                    "producer": pdf_metadata.get("producer") or None,
                    "creation_date": pdf_metadata.get("creationDate") or None,
                    "modification_date": pdf_metadata.get("modDate") or None
                },

                "page_count": document.page_count,
                "pages_with_text": pages_with_text,
                "pages_without_text": pages_without_text,
                "pages_ocr": pages_ocr,
                "total_characters": len(full_text),

                "extraction_status": (
                    "success" if full_text else "no_text_detected"
                ),

                "pages": pages,
                "text": full_text
            }

    except (FileNotFoundError, ValueError):
        raise

    except pytesseract.TesseractNotFoundError as error:
        raise RuntimeError(
            "Tesseract OCR was not found. Install it using: "
            "sudo apt install tesseract-ocr tesseract-ocr-eng"
        ) from error

    except pytesseract.TesseractError as error:
        raise RuntimeError(
            f"Tesseract OCR failed: {error}"
        ) from error

    except Exception as error:
        raise RuntimeError(
            f"Unable to process PDF: {error}"
        ) from error
