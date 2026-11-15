
from pathlib import Path
import re
import pymupdf


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



    """Detect multiple author names from the first PDF page."""

    author_pattern = re.compile(
        r"^[^\W\d_][\w.'’\-]*(?:\s+[^\W\d_][\w.'’\-]*)*,\s*"
        r"[^\W\d_][\w.'’\-]*(?:\s+[^\W\d_][\w.'’\-]*)*$",
        re.UNICODE
    )

    authors = []
    seen = set()

    # Retrieve individual text blocks from the cover page.
    blocks = page.get_text("blocks", sort=True)

    for block in blocks:
        block_text = block[4]

        for raw_line in block_text.splitlines():

            # Remove invisible characters and normalize whitespace.
            line = raw_line.replace("\u200b", "")
            line = re.sub(r"\s+", " ", line).strip()

            # Identify names using the "Surname, Given Name" format.
            if author_pattern.fullmatch(line):

                if line.casefold() not in seen:
                    authors.append(line)
                    seen.add(line.casefold())

    return authors


def extract_cover_authors(page):
    """Extract multiple authors from the cover page."""

    author_pattern = re.compile(
        r"^[^\W\d_][\w.'’\-]*(?:\s+[^\W\d_][\w.'’\-]*)*,\s*"
        r"[^\W\d_][\w.'’\-]*(?:\s+[^\W\d_][\w.'’\-]*)*$",
        re.UNICODE
    )

    blocks = page.get_text("blocks", sort=True)

    # Collect and clean individual lines from text blocks.
    lines = []

    for block in blocks:
        for raw_line in block[4].splitlines():
            line = raw_line.replace("\u200b", "")
            line = re.sub(r"\s+", " ", line).strip()

            if line:
                lines.append(line)

    # Locate the beginning of the author section.
    anchor_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "partial fulfillment" in line.casefold()
        ),
        None
    )

    if anchor_index is not None:
        # Only inspect content appearing after the academic requirement.
        candidate_lines = lines[anchor_index + 1:]
    else:
        # Fallback for documents without the expected cover-page phrase.
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

        # Stop when the publication date is encountered.
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


def extract_pdf(pdf_path):
    """Extract metadata and cleaned page-by-page text from a PDF."""

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

                raw_text = page.get_text(
                    "text",
                    sort=True
                ).strip()

                cleaned_text = clean_page_text(raw_text)

                pages.append({
                    "page_number": page_number,
                    "raw_text": raw_text,
                    "text": cleaned_text,
                    "character_count": len(cleaned_text)
                })

            full_text = "\n\n".join(
                f"[Page {page['page_number']}]\n{page['text']}"
                for page in pages
                if page["text"]
            )

            metadata = document.metadata or {}

            # Extract all authors from the first page.
            authors = extract_cover_authors(document[0])

            # Use PDF metadata as a fallback.
            if not authors and metadata.get("author"):
                authors = [metadata["author"].strip()]

            pages_with_text = sum(
                1 for page in pages if page["text"]
            )

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
                "pages_without_text": document.page_count - pages_with_text,
                "total_characters": len(full_text),

                "extraction_status": (
                    "success" if full_text else "no_text_detected"
                ),

                "pages": pages,
                "text": full_text
            }

    except (FileNotFoundError, ValueError):
        raise

    except Exception as error:
        raise RuntimeError(
            f"Unable to process PDF: {error}"
        ) from error
