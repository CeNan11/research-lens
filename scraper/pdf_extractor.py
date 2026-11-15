
from pathlib import Path
import re

import pymupdf
import pytesseract
from PIL import Image


# Pages with fewer characters than this may need OCR
OCR_TEXT_THRESHOLD = 80

# OCR rendering resolution
OCR_DPI = 300


def clean_page_text(raw_text):
    """Clean extracted PDF text while preserving paragraphs."""

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
    """Render a PDF page and extract its text using Tesseract."""

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


def extract_author_lines(lines):
    """Identify author names from cover-page text lines."""

    author_pattern = re.compile(
        r"^[^\W\d_][\w.'’\-]*(?:\s+[^\W\d_][\w.'’\-]*)*,\s*"
        r"[^\W\d_][\w.'’\-]*(?:\s+[^\W\d_][\w.'’\-]*)*$",
        re.UNICODE
    )

    anchor_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "partial fulfillment" in line.casefold()
        ),
        None
    )

    if anchor_index is not None:
        candidate_lines = lines[anchor_index + 1:]
    else:
        excluded_terms = (
            "university", "college", "department", "school",
            "philippines", "davao", "city", "barangay",
            "bo.", "street", "road", "avenue", "campus",
            "institute"
        )

        candidate_lines = [
            line for line in lines
            if not any(
                term in line.casefold()
                for term in excluded_terms
            )
        ]

    authors = []
    seen = set()

    for line in candidate_lines:

        # Stop at a publication date.
        if re.search(
            r"\b(?:January|February|March|April|May|June|July|"
            r"August|September|October|November|December)\s+"
            r"\d{1,2},?\s+\d{4}\b",
            line,
            re.IGNORECASE
        ):
            break

        if author_pattern.fullmatch(line):
            if line.casefold() not in seen:
                authors.append(line)
                seen.add(line.casefold())

    return authors


def extract_cover_authors(page, fallback_text=None):
    """Extract authors from native PDF text or OCR text."""

    lines = []

    blocks = page.get_text("blocks", sort=True)

    for block in blocks:
        for raw_line in block[4].splitlines():
            line = raw_line.replace("\u200b", "")
            line = re.sub(r"\s+", " ", line).strip()

            if line:
                lines.append(line)

    authors = extract_author_lines(lines)

    # Use OCR text if native PDF extraction found no authors.
    if not authors and fallback_text:
        fallback_lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in fallback_text.splitlines()
            if line.strip()
        ]

        authors = extract_author_lines(fallback_lines)

    return authors


def extract_pdf(pdf_path):
    """Extract PDF metadata and page-by-page text with OCR fallback."""

    pdf_file = Path(pdf_path).expanduser()

    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_file}")

    if not pdf_file.is_file():
        raise ValueError("The supplied path is not a file.")

    if pdf_file.suffix.lower() != ".pdf":
        raise ValueError("The supplied file must be a PDF.")

    try:
        with pymupdf.open(str(pdf_file)) as document:

            if document.needs_pass:
                raise ValueError("This PDF is password-protected.")

            pages = []

            for page_number, page in enumerate(document, start=1):

                # First attempt: extract selectable text.
                native_text = page.get_text(
                    "text",
                    sort=True
                ).strip()

                # Check whether the page contains embedded images.
                has_images = bool(page.get_images(full=True))

                ocr_attempted = False
                ocr_text = ""

                final_text = native_text
                extraction_method = (
                    "text" if native_text else "none"
                )

                # Second attempt: use OCR when the page is image-based
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

            # Combine all pages while preserving page references.
            full_text = "\n\n".join(
                f"[Page {page['page_number']}]\n{page['text']}"
                for page in pages
                if page["text"]
            )

            metadata = document.metadata or {}

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

            # Extract multiple authors from the first page.
            first_page_ocr = pages[0]["text"] if pages else None

            authors = extract_cover_authors(
                document[0],
                fallback_text=first_page_ocr
            ) if document.page_count else []

            # Fall back to internal PDF metadata.
            if not authors and metadata.get("author"):
                authors = [metadata["author"].strip()]

            return {
                "source_type": "pdf",
                "file_name": pdf_file.name,

                "metadata": {
                    "title": metadata.get("title") or None,
                    "authors": authors,
                    "pdf_author_metadata": metadata.get("author") or None,
                    "subject": metadata.get("subject") or None,
                    "keywords": metadata.get("keywords") or None,
                    "creator": metadata.get("creator") or None,
                    "producer": metadata.get("producer") or None,
                    "creation_date": metadata.get("creationDate") or None,
                    "modification_date": metadata.get("modDate") or None
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
