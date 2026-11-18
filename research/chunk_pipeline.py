
from pathlib import Path


def get_source_name(value):
    """Normalize a source filename for comparison."""

    if not value:
        return None

    return Path(str(value)).name.strip().casefold()


def validate_chunk_inputs(profile, pdf_data, chunks_data):
    """Validate the approved profile and matching PDF data."""

    if not isinstance(profile, dict):
        raise TypeError("Research profile must be a dictionary.")

    if not isinstance(pdf_data, dict):
        raise TypeError("PDF extraction result must be a dictionary.")

    if not isinstance(chunks_data, dict):
        raise TypeError("Chunk extraction result must be a dictionary.")

    if profile.get("review", {}).get("status") != "approved":
        raise ValueError(
            "The research profile has not been approved. "
            "Open the profile editor and select option 7 "
            "to approve and save it."
        )

    if pdf_data.get("source_type") != "pdf":
        raise ValueError("The selected source is not a PDF extraction result.")

    if chunks_data.get("source_type") != "research_chunks":
        raise ValueError("The selected data is not a ResearchLens chunk result.")

    profile_source = get_source_name(
        profile.get("source", {}).get("file_name")
    )

    pdf_source = get_source_name(
        pdf_data.get("file_name")
    )

    chunks_source = get_source_name(
        chunks_data.get("source_file")
    )

    if not profile_source or not pdf_source or not chunks_source:
        raise ValueError(
            "One or more files are missing their original PDF filename."
        )

    if profile_source != pdf_source or pdf_source != chunks_source:
        raise ValueError(
            "The selected research profile, PDF extraction, and chunks "
            "do not all originate from the same PDF.\n"
            f"Profile source: {profile_source}\n"
            f"PDF source: {pdf_source}\n"
            f"Chunk source: {chunks_source}"
        )

    if not isinstance(profile.get("research"), dict):
        raise ValueError("The research profile has no research data.")

    if not isinstance(
        profile["research"].get("sections"),
        dict
    ):
        raise ValueError("The research profile has no section information.")

    chunks = chunks_data.get("chunks")

    if not isinstance(chunks, list) or not chunks:
        raise ValueError("No chunks were found in the processing result.")

    return True


def build_chunk_package(profile, pdf_data, chunks_data):
    """
    Link generated chunks to an approved research profile.

    Chunks remain traceable to their original PDF extraction.
    Profile sections and manual edits are preserved separately.
    """

    validate_chunk_inputs(
        profile,
        pdf_data,
        chunks_data
    )

    research = profile["research"]
    profile_sections = research["sections"]

    # Create a group for each section in the approved profile.
    grouped_sections = {}

    for section_key, section_data in profile_sections.items():

        manually_edited = (
            section_data.get("content_source") == "manual"
        )

        grouped_sections[section_key] = {
            "section_key": section_key,
            "heading": section_data.get("heading", []),
            "profile_status": section_data.get("status", "not_found"),
            "profile_pages": section_data.get("pages", []),
            "profile_content_manually_edited": manually_edited,
            "profile_content": section_data.get("content", ""),
            "chunk_count": 0,
            "chunks": [],
        }

    unclassified_chunks = []
    unmapped_chunks = []

    # Assign each chunk to its corresponding research section.
    for chunk in chunks_data["chunks"]:

        section_key = chunk.get("section")

        if section_key is None:
            unclassified_chunks.append(chunk)
            continue

        if section_key not in grouped_sections:

            unmapped_chunks.append({
                "reason": "Section key not found in approved profile.",
                "chunk": chunk,
            })

            continue

        grouped_sections[section_key]["chunks"].append(chunk)

    # Count chunks in each research section.
    for section in grouped_sections.values():
        section["chunk_count"] = len(section["chunks"])

    # Identify profile sections that were manually edited.
    manually_edited_sections = [
        section_key
        for section_key, section in grouped_sections.items()
        if section["profile_content_manually_edited"]
    ]

    warnings = []

    if manually_edited_sections:
        warnings.append(
            "Some approved profile sections were manually edited. "
            "The chunks still contain text from the original PDF "
            "extraction and do not automatically incorporate those edits."
        )

    if unclassified_chunks:
        warnings.append(
            "Some chunks could not be assigned to a research section. "
            "Their original text and page references have been preserved."
        )

    if unmapped_chunks:
        warnings.append(
            "Some chunks refer to section keys that do not exist "
            "in the approved profile."
        )

    total_chunks = len(chunks_data["chunks"])

    grouped_chunk_count = sum(
        section["chunk_count"]
        for section in grouped_sections.values()
    )

    return {
        "package_version": "1.0",

        "source": {
            "file_name": pdf_data.get("file_name"),
            "page_count": pdf_data.get("page_count"),
            "pdf_extraction_status": pdf_data.get("extraction_status"),
        },

        "profile_review": {
            "status": profile["review"]["status"],
            "profile_version": profile.get("profile_version"),
            "manual_edits": profile["review"].get("manual_edits", []),
            "manually_edited_sections": manually_edited_sections,
        },

        # Preserve the full approved research profile.
        "research_profile": research,

        "chunk_processing": {
            "config": chunks_data.get("processing_config", {}),
            "total_paragraphs": chunks_data.get("total_paragraphs", 0),
            "total_chunks": total_chunks,
            "grouped_chunks": grouped_chunk_count,
            "unclassified_chunks": len(unclassified_chunks),
            "unmapped_chunks": len(unmapped_chunks),
        },

        "sections": grouped_sections,

        "unclassified_chunks": unclassified_chunks,

        "unmapped_chunks": unmapped_chunks,

        "validation": {
            "profile_approved": True,
            "source_files_match": True,
            "all_chunks_accounted_for": (
                grouped_chunk_count
                + len(unclassified_chunks)
                + len(unmapped_chunks)
                == total_chunks
            ),
            "warnings": warnings,
        },
    }
