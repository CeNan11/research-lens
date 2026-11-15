
from pathlib import Path
import pymupdf


def extract_pdf(pdf_path):
    """Extract metadata and page-by-page text from a PDF."""

    pdf_file = Path(pdf_path).expanduser()

    # Validate the supplied file.
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_file}")

    if not pdf_file.is_file():
        raise ValueError("The supplied path is not a file.")

    if pdf_file.suffix.lower() != ".pdf":
        raise ValueError("The supplied file must be a PDF.")

    try:
        with pymupdf.open(str(pdf_file)) as document:

            if document.needs_pass:
                raise ValueError(
                    "This PDF is password-protected."
                )

            # Extract text separately for each page.
            pages = []

            for page_number, page in enumerate(document, start=1):
                page_text = page.get_text(
                    "text",
                    sort=True
                ).strip()

                pages.append({
                    "page_number": page_number,
                    "text": page_text,
                    "character_count": len(page_text)
                })

            # Combine extracted text while preserving page references.
            full_text = "\n\n".join(
                f"[Page {page['page_number']}]\n{page['text']}"
                for page in pages
                if page["text"]
            )

            # Extract available PDF metadata.
            metadata = document.metadata or {}

            return {
                "source_type": "pdf",
                "file_name": pdf_file.name,

                "metadata": {
                    "title": metadata.get("title"),
                    "author": metadata.get("author"),
                    "subject": metadata.get("subject"),
                    "keywords": metadata.get("keywords"),
                    "creator": metadata.get("creator"),
                    "producer": metadata.get("producer"),
                    "creation_date": metadata.get("creationDate"),
                    "modification_date": metadata.get("modDate")
                },

                "page_count": document.page_count,
                "pages_with_text": sum(
                    1 for page in pages if page["text"]
                ),
                "total_characters": len(full_text),

                "extraction_status": (
                    "success" if full_text else "no_text_detected"
                ),

                "pages": pages,
                "text": full_text
            }

    except Exception as error:
        raise RuntimeError(
            f"Unable to process PDF: {error}"
        ) from error
