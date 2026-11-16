
import re


# Research sections and their common heading variations.
SECTION_ALIASES = {
    "abstract": [
        "abstract",
    ],
    "background_of_study": [
        "background of the study",
        "background of study",
        "rationale of the study",
        "introduction",
    ],
    "statement_of_problem": [
        "statement of the problem",
        "problem statement",
    ],
    "objectives": [
        "objectives of the study",
        "research objectives",
        "general objective",
        "general objectives",
        "specific objective",
        "specific objectives",
        "objectives",
    ],
    "research_questions": [
        "research questions",
        "research question",
        "statement of research questions",
    ],
    "scope_and_limitations": [
        "scope and limitations",
        "scope and delimitations",
        "scope of the study",
        "delimitations and limitations",
        "limitations of the study",
    ],
    "significance_of_study": [
        "significance of the study",
        "significance of the research",
    ],
    "methodology": [
        "research methodology",
        "methodology",
        "research methods",
        "research design",
        "methods",
    ],
    "theoretical_framework": [
        "theoretical framework",
    ],
    "conceptual_framework": [
        "conceptual framework",
    ],
    "review_of_related_literature": [
        "review of related literature",
        "review of related studies",
        "related literature and studies",
        "review of related literature and studies",
        "literature review",
    ],
}


def normalize_text(text):
    """Normalize whitespace and remove surrounding spaces."""
    return re.sub(r"\s+", " ", str(text)).strip()


def normalize_heading(line):
    """
    Normalize a heading so that numbering, capitalization,
    and trailing punctuation do not prevent recognition.
    """

    heading = normalize_text(line)

    # Remove common chapter prefixes.
    heading = re.sub(
        r"^chapter\s+(?:[ivxlcdm]+|\d+)\s*[:.\-–—]?\s*",
        "",
        heading,
        flags=re.IGNORECASE
    )

    # Remove section numbering, such as 1., 1.1, or 2.3.1.
    heading = re.sub(
        r"^\d+(?:\.\d+)*\.?\s*",
        "",
        heading
    )

    # Remove common trailing labels.
    heading = re.sub(
        r"\s*\(continued\)\s*$",
        "",
        heading,
        flags=re.IGNORECASE
    )

    return heading.strip(" \t:.-–—").casefold()


# Build a lookup table for heading recognition.
HEADING_LOOKUP = {
    normalize_heading(alias): section_key
    for section_key, aliases in SECTION_ALIASES.items()
    for alias in aliases
}


def detect_section_heading(line):
    """Return the profile field when a recognized heading is found."""

    normalized = normalize_heading(line)
    return HEADING_LOOKUP.get(normalized)


def is_document_boundary(line):
    """
    Detect headings that should stop the current section,
    even though they are not profile fields.
    """

    normalized = normalize_heading(line)

    if re.fullmatch(
        r"chapter\s+(?:[ivxlcdm]+|\d+)",
        normalize_text(line),
        flags=re.IGNORECASE
    ):
        return True

    boundaries = {
        "references",
        "bibliography",
        "appendix",
        "appendices",
        "list of figures",
        "list of tables",
        "table of contents",
        "acknowledgement",
        "acknowledgements",
        "acknowledgment",
        "acknowledgments",
    }

    return normalized in boundaries


def get_page_text(page):
    """Get usable text from a page extraction result."""

    return (
        page.get("text")
        or page.get("raw_text")
        or page.get("ocr_text")
        or ""
    )


def extract_sections(pages):
    """
    Detect recognized research sections and collect their contents.

    Page numbers are preserved so extracted information can
    later be traced back to the original PDF.
    """

    sections = {
        key: {
            "heading": [],
            "content_parts": [],
            "pages": [],
        }
        for key in SECTION_ALIASES
    }

    current_section = None

    for page_index, page in enumerate(pages, start=1):

        page_number = page.get("page_number", page_index)
        page_text = get_page_text(page)

        for raw_line in page_text.splitlines():

            line = normalize_text(raw_line)

            if not line:
                continue

            detected_section = detect_section_heading(line)

            if detected_section:
                current_section = detected_section

                if line not in sections[current_section]["heading"]:
                    sections[current_section]["heading"].append(line)

                if page_number not in sections[current_section]["pages"]:
                    sections[current_section]["pages"].append(page_number)

                continue

            if is_document_boundary(line):
                current_section = None
                continue

            if current_section:
                section = sections[current_section]

                section["content_parts"].append(line)

                if page_number not in section["pages"]:
                    section["pages"].append(page_number)

    # Prepare the final section structure.
    extracted_sections = {}

    for key, section in sections.items():

        content = "\n\n".join(section["content_parts"]).strip()

        extracted_sections[key] = {
            "heading": section["heading"],
            "content": content,
            "pages": sorted(section["pages"]),
            "status": (
                "found" if content
                else "heading_found_no_content"
                if section["heading"]
                else "not_found"
            ),
        }

    return extracted_sections


def extract_explicit_keywords(pages, pdf_metadata):
    """
    Extract keywords explicitly provided in the PDF text
    or its embedded metadata.

    This does not generate or guess keywords.
    """

    keyword_pattern = re.compile(
        r"^(?:keywords?|key\s*words?|index\s*terms?)"
        r"\s*[:\-–—]\s*(.+)$",
        re.IGNORECASE
    )

    for page_index, page in enumerate(pages, start=1):

        page_number = page.get("page_number", page_index)

        for line in get_page_text(page).splitlines():

            match = keyword_pattern.match(normalize_text(line))

            if match:
                raw_keywords = match.group(1)

                keywords = [
                    normalize_text(item).strip(" .")
                    for item in re.split(r"[,;•]", raw_keywords)
                    if normalize_text(item).strip(" .")
                ]

                if keywords:
                    return {
                        "items": keywords,
                        "source": "document_text",
                        "pages": [page_number],
                    }

    metadata_keywords = pdf_metadata.get("keywords")

    if metadata_keywords:
        keywords = [
            normalize_text(item).strip(" .")
            for item in re.split(r"[,;]", metadata_keywords)
            if normalize_text(item).strip(" .")
        ]

        if keywords:
            return {
                "items": keywords,
                "source": "pdf_metadata",
                "pages": [],
            }

    return {
        "items": [],
        "source": None,
        "pages": [],
    }


def build_research_profile(pdf_data):
    """
    Build a structured research profile from the output
    produced by scraper.pdf_extractor.extract_pdf().
    """

    if not isinstance(pdf_data, dict):
        raise TypeError("PDF extraction result must be a dictionary.")

    pages = pdf_data.get("pages", [])

    if not isinstance(pages, list):
        raise ValueError("PDF extraction result has an invalid pages field.")

    metadata = pdf_data.get("metadata") or {}

    if not isinstance(metadata, dict):
        metadata = {}

    title = metadata.get("title")
    authors = metadata.get("authors") or []

    sections = extract_sections(pages)

    keywords = extract_explicit_keywords(
        pages,
        metadata
    )

    missing_sections = [
        key
        for key, section in sections.items()
        if section["status"] != "found"
    ]

    missing_fields = []

    if not title:
        missing_fields.append("title")

    if not authors:
        missing_fields.append("authors")

    if not keywords["items"]:
        missing_fields.append("keywords")

    missing_fields.extend(missing_sections)

    return {
        "profile_version": "1.0",

        "source": {
            "file_name": pdf_data.get("file_name"),
            "page_count": pdf_data.get("page_count", len(pages)),
            "extraction_status": pdf_data.get("extraction_status"),
        },

        "research": {
            "title": title,
            "title_source": metadata.get("title_extraction_method"),
            "authors": authors,
            "keywords": keywords,
            "sections": sections,
        },

        "review": {
            "status": "pending",
            "missing_fields": missing_fields,
        },
    }
