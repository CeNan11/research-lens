
import re


# ---------------------------------------------------------
# RESEARCH SECTION DEFINITIONS
# ---------------------------------------------------------

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
        "scope and limitation",
        "scope and delimitation",
        "scope and delimitations",
        "scope of the study",
        "scope of study",
        "delimitations of the study",
        "delimitation of the study",
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
        "review of related literature and studies",
        "review of related literature",
        "review of related studies",
        "related literature and studies",
        "related literature",
        "literature review",
    ],
}


# Build a lookup table for faster heading recognition.
HEADING_LOOKUP = {
    alias: section_key
    for section_key, aliases in SECTION_ALIASES.items()
    for alias in aliases
}


# ---------------------------------------------------------
# TEXT NORMALIZATION
# ---------------------------------------------------------

def normalize_text(text):
    """Normalize whitespace and remove invisible characters."""

    text = str(text)

    text = text.replace("\u00a0", " ")
    text = text.replace("\u00ad", "")
    text = text.replace("\u200b", "")

    return re.sub(r"\s+", " ", text).strip()


def normalize_heading(line):
    """
    Normalize a heading by removing chapter numbers,
    section numbering, capitalization differences,
    and trailing punctuation.
    """

    heading = normalize_text(line)

    # Remove prefixes such as:
    # Chapter 1:
    # Chapter II -
    # CHAPTER 2.
    heading = re.sub(
        r"^chapter\s+(?:[ivxlcdm]+|\d+)\s*[:.\-–—]?\s*",
        "",
        heading,
        flags=re.IGNORECASE
    )

    # Remove numbering such as:
    # 1. Background
    # 1.1 Background
    # 2.3.1 Objectives
    heading = re.sub(
        r"^\d+(?:\.\d+)*[.)]?\s*",
        "",
        heading
    )

    heading = heading.strip(" \t:.-–—")
    
    return heading.casefold()


# ---------------------------------------------------------
# HEADING DETECTION
# ---------------------------------------------------------

def match_section_heading(line):
    """
    Identify a section heading.

    Returns:
        (section_key, remaining_text)

    remaining_text contains any paragraph text that appears
    after a heading on the same line.
    """

    original_line = normalize_text(line)

    if not original_line:
        return None, ""

    normalized = normalize_heading(original_line)

    # First try an exact heading match.
    if normalized in HEADING_LOOKUP:
        return HEADING_LOOKUP[normalized], ""

    # Remove chapter and section numbering before checking
    # for a heading followed by text on the same line.
    candidate = re.sub(
        r"^chapter\s+(?:[ivxlcdm]+|\d+)\s*[:.\-–—]?\s*",
        "",
        original_line,
        flags=re.IGNORECASE
    )

    candidate = re.sub(
        r"^\d+(?:\.\d+)*[.)]?\s*",
        "",
        candidate
    )

    candidate_lower = candidate.casefold()

    # Check longer aliases first to avoid matching a shorter
    # alias before a more specific heading.
    aliases = sorted(
        HEADING_LOOKUP.keys(),
        key=len,
        reverse=True
    )

    for alias in aliases:

        if not candidate_lower.startswith(alias):
            continue

        # Require a valid boundary after the heading.
        if len(candidate) > len(alias):
            next_character = candidate[len(alias)]

            if not (
                next_character.isspace()
                or next_character in ":.-–—"
            ):
                continue

        section_key = HEADING_LOOKUP[alias]

        remaining_text = candidate[len(alias):]
        remaining_text = remaining_text.strip(" \t:.-–—")

        return section_key, remaining_text

    return None, ""


def detect_section_heading(line):
    """Return the section key when a heading is recognized."""

    section_key, _ = match_section_heading(line)

    return section_key


# ---------------------------------------------------------
# DOCUMENT BOUNDARIES
# ---------------------------------------------------------

def is_document_boundary(line):
    """
    Identify headings that should stop the current section.

    These are not necessarily research profile fields.
    """

    normalized = normalize_heading(line)

    # Stop at a new chapter if it is not a recognized
    # section heading.
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


# ---------------------------------------------------------
# PAGE TEXT SELECTION
# ---------------------------------------------------------

def get_page_text(page):
    """
    Select the most appropriate text source.

    Native PDF pages:
        Prefer original selectable text.

    OCR pages:
        Prefer original OCR output.

    Cleaned text is used as a fallback.
    """

    extraction_method = page.get("extraction_method")

    if extraction_method == "ocr":
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
        if candidate and candidate.strip():
            return candidate

    return ""


# ---------------------------------------------------------
# SECTION EXTRACTION
# ---------------------------------------------------------

def extract_sections(pages):
    """
    Detect research sections and collect their contents.

    Page numbers are preserved so researchers can trace
    extracted information back to the original PDF.
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

            # Check for a recognized research heading.
            detected_section, remaining_text = (
                match_section_heading(line)
            )

            if detected_section:

                current_section = detected_section

                section = sections[current_section]

                if line not in section["heading"]:
                    section["heading"].append(line)

                if page_number not in section["pages"]:
                    section["pages"].append(page_number)

                # Some PDFs put heading and paragraph text
                # on the same line. Preserve that paragraph.
                if remaining_text:
                    section["content_parts"].append(
                        remaining_text
                    )

                continue

            # Stop collecting text at document boundaries.
            if is_document_boundary(line):
                current_section = None
                continue

            # Collect text under the current section.
            if current_section:

                section = sections[current_section]

                section["content_parts"].append(line)

                if page_number not in section["pages"]:
                    section["pages"].append(page_number)

    # Prepare the final section structure.
    extracted_sections = {}

    for key, section in sections.items():

        content = "\n".join(
            section["content_parts"]
        ).strip()

        extracted_sections[key] = {
            "heading": section["heading"],
            "content": content,
            "pages": sorted(section["pages"]),
            "status": (
                "found"
                if content
                else "heading_found_no_content"
                if section["heading"]
                else "not_found"
            ),
        }

    return extracted_sections


# ---------------------------------------------------------
# KEYWORD EXTRACTION
# ---------------------------------------------------------

def extract_explicit_keywords(pages, pdf_metadata):
    """
    Extract keywords explicitly provided in the document
    or embedded PDF metadata.

    This function does not invent or generate keywords.
    """

    keyword_pattern = re.compile(
        r"^(?:keywords?|key\s*words?|index\s*terms?)"
        r"\s*[:\-–—]\s*(.+)$",
        re.IGNORECASE
    )

    for page_index, page in enumerate(pages, start=1):

        page_number = page.get("page_number", page_index)

        for line in get_page_text(page).splitlines():

            line = normalize_text(line)

            match = keyword_pattern.match(line)

            if not match:
                continue

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

    # Fall back to embedded PDF metadata.
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


# ---------------------------------------------------------
# RESEARCH PROFILE BUILDER
# ---------------------------------------------------------

def build_research_profile(pdf_data):
    """
    Build a structured research profile from the output
    produced by scraper.pdf_extractor.extract_pdf().
    """

    if not isinstance(pdf_data, dict):
        raise TypeError(
            "PDF extraction result must be a dictionary."
        )

    pages = pdf_data.get("pages", [])

    if not isinstance(pages, list):
        raise ValueError(
            "PDF extraction result has an invalid pages field."
        )

    metadata = pdf_data.get("metadata") or {}

    if not isinstance(metadata, dict):
        metadata = {}

    title = metadata.get("title")

    authors = metadata.get("authors") or []

    # Support PDFs where author metadata is a single string.
    if isinstance(authors, str):
        authors = [authors] if authors.strip() else []

    # Extract research sections.
    sections = extract_sections(pages)

    # Extract explicitly stated keywords.
    keywords = extract_explicit_keywords(
        pages,
        metadata
    )

    # Identify fields that still need researcher review.
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

    # Build the final profile.
    return {
        "profile_version": "1.0",

        "source": {
            "file_name": pdf_data.get("file_name"),
            "page_count": pdf_data.get(
                "page_count",
                len(pages)
            ),
            "extraction_status": pdf_data.get(
                "extraction_status"
            ),
        },

        "research": {
            "title": title,
            "title_source": metadata.get(
                "title_extraction_method"
            ),
            "authors": authors,
            "keywords": keywords,
            "sections": sections,
        },

        "review": {
            "status": "pending",
            "missing_fields": missing_fields,
        },
    }
