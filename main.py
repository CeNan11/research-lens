
import json
import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

from scraper.web_scraper import scrape_article
from scraper.pdf_extractor import extract_pdf

from research.profile_extractor import build_research_profile
from research.profile_editor import (
    run_profile_editor,
    validate_profile,
)

from research.text_processor import process_pdf_extraction
from research.chunk_pipeline import build_chunk_package


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

def generate_filename(filename):
    """Generate a filesystem-safe filename."""

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        Path(filename).stem.lower()
    ).strip("-")

    return slug or "document"


def save_json(data, output_folder, filename):
    """Save data as JSON without overwriting existing files."""

    output_dir = Path(output_folder)
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = generate_filename(filename)
    output_file = output_dir / f"{base_name}.json"

    counter = 2

    while output_file.exists():
        output_file = output_dir / f"{base_name}-{counter}.json"
        counter += 1

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(f"\nSaved to: {output_file}")

    return output_file


def load_json(file_path):
    """Load a JSON file."""

    with Path(file_path).open("r", encoding="utf-8") as file:
        return json.load(file)


# ---------------------------------------------------------
# FILE SELECTORS
# ---------------------------------------------------------

def select_pdf():
    """Open a PDF file selector."""

    input_directory = Path("input/pdfs")
    input_directory.mkdir(parents=True, exist_ok=True)

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        return filedialog.askopenfilename(
            title="Select a Research Paper",
            initialdir=str(input_directory.resolve()),
            filetypes=[
                ("PDF Documents", "*.pdf"),
                ("All Files", "*.*")
            ]
        )

    finally:
        root.destroy()


def select_json(title, initial_directory):
    """Open a JSON file selector."""

    directory = Path(initial_directory)
    directory.mkdir(parents=True, exist_ok=True)

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        return filedialog.askopenfilename(
            title=title,
            initialdir=str(directory.resolve()),
            filetypes=[
                ("JSON Files", "*.json"),
                ("All Files", "*.*")
            ]
        )

    finally:
        root.destroy()


# ---------------------------------------------------------
# PHASE 1: WEBSITE ARTICLE EXTRACTION
# ---------------------------------------------------------

def run_website_scraper():
    """Handle website article extraction."""

    url = input("\nEnter article URL: ").strip()

    if not url:
        print("No URL provided.")
        return

    try:
        article = scrape_article(url)

        if not article:
            print("Unable to extract article.")
            return

        print("\n========== ARTICLE INFORMATION ==========")

        print(f"Title: {article['title']}")
        print(f"Author: {article['author']}")
        print(f"Date: {article['date']}")
        print(f"Website: {article['website']}")

        print("\n========== ARTICLE CONTENT ==========")

        content = article["text"]

        print(content[:1500])
        print(f"\nTotal characters: {len(content)}")

        save_json(
            article,
            "output/articles",
            article.get("title") or "article"
        )

    except Exception as error:
        print(f"\nArticle extraction failed: {error}")


# ---------------------------------------------------------
# PHASE 2: PDF EXTRACTION
# ---------------------------------------------------------

def run_pdf_extractor():
    """Handle PDF extraction."""

    print("\nOpening PDF file selector...")

    pdf_path = select_pdf()

    if not pdf_path:
        print("No PDF selected.")
        return

    try:
        result = extract_pdf(pdf_path)
        metadata = result["metadata"]

        print("\n========== PDF INFORMATION ==========")

        print(f"File: {result['file_name']}")
        print(f"Title: {metadata['title']}")

        print("\nAuthors:")

        for index, author in enumerate(metadata["authors"], start=1):
            print(f"{index}. {author}")

        if not metadata["authors"]:
            print("No authors detected.")

        print(f"Pages: {result['page_count']}")
        print(f"Pages with text: {result['pages_with_text']}")
        print(f"Pages processed with OCR: {result['pages_ocr']}")
        print(f"Pages without text: {result['pages_without_text']}")
        print(f"Total characters: {result['total_characters']}")

        print("\n========== EXTRACTION RESULT ==========")

        print(result["text"][:2000])
        print("\nShowing first 2,000 characters.")

        save_json(
            result,
            "output/pdfs",
            result["file_name"]
        )

    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"\nPDF extraction failed: {error}")


# ---------------------------------------------------------
# PHASE 3: RESEARCH PROFILE CREATION
# ---------------------------------------------------------

def run_profile_creator():
    """Create a research profile from an extracted PDF JSON."""

    print("\n========== CREATE RESEARCH PROFILE ==========")
    print("Select an extracted PDF JSON file from output/pdfs.")

    source_path = select_json(
        title="Select an Extracted PDF",
        initial_directory="output/pdfs"
    )

    if not source_path:
        print("No PDF extraction file selected.")
        return

    try:
        pdf_data = load_json(source_path)

        if not isinstance(pdf_data, dict):
            raise ValueError(
                "The selected JSON is not a valid PDF extraction result."
            )

        if pdf_data.get("source_type") != "pdf":
            raise ValueError(
                "The selected JSON is not a ResearchLens PDF extraction."
            )

        if not isinstance(pdf_data.get("pages"), list):
            raise ValueError(
                "The selected PDF JSON has no valid pages."
            )

        print("\nGenerating research profile...")

        profile = build_research_profile(pdf_data)

        research = profile["research"]

        print("\n========== RESEARCH PROFILE GENERATED ==========")

        print("Title:", research.get("title") or "Not detected")

        print("\nAuthors:")

        if research.get("authors"):
            for author in research["authors"]:
                print(f"- {author}")
        else:
            print("No authors detected.")

        print("\nDetected research sections:")

        found_sections = 0

        for name, section in research["sections"].items():

            if section["status"] == "found":
                found_sections += 1

                print(
                    f"- {name.replace('_', ' ').title()} "
                    f"| Pages: {section['pages']}"
                )

        if found_sections == 0:
            print("No research sections detected.")

        print(f"\nTotal sections detected: {found_sections}")

        # Save the generated profile.
        profile_filename = (
            f"{Path(source_path).stem}_profile.json"
        )

        profile_path = save_json(
            profile,
            "output/profiles",
            profile_filename
        )

        # Automatically open the profile editor.
        print("\nOpening Research Profile Editor...")

        run_profile_editor(
            profile,
            profile_path
        )

    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
        KeyError
    ) as error:

        print(f"\nResearch profile creation failed: {error}")


# ---------------------------------------------------------
# PHASE 3: EXISTING PROFILE REVIEW
# ---------------------------------------------------------

def run_existing_profile_editor():
    """Open an existing research profile for review or editing."""

    print("\n========== REVIEW EXISTING RESEARCH PROFILE ==========")

    profile_path = select_json(
        title="Select a Research Profile",
        initial_directory="output/profiles"
    )

    if not profile_path:
        print("No research profile selected.")
        return

    try:
        profile = load_json(profile_path)

        profile = validate_profile(profile)

        print("\nOpening Research Profile Editor...")

        run_profile_editor(
            profile,
            Path(profile_path)
        )

    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
        ValueError
    ) as error:

        print(f"\nUnable to open research profile: {error}")


# ---------------------------------------------------------
# PHASE 4: CHUNK PROCESSING AND PROFILE LINKING
# ---------------------------------------------------------

def run_chunk_pipeline():
    """
    Generate research chunks and link them to an
    approved research profile.
    """

    print("\n========== GENERATE RESEARCH CHUNKS ==========")

    # Step 1: Select the approved research profile.
    print("\nSelect an APPROVED research profile.")

    profile_path = select_json(
        title="Select an Approved Research Profile",
        initial_directory="output/profiles"
    )

    if not profile_path:
        print("No research profile selected.")
        return

    try:
        profile = load_json(profile_path)
        profile = validate_profile(profile)

        if profile.get("review", {}).get("status") != "approved":
            print("\nThis research profile has not been approved.")
            print(
                "Open option 4, review the profile, "
                "and use option 7 to approve and save it."
            )
            return

        # Step 2: Select the original PDF extraction JSON.
        print("\nSelect the matching PDF extraction JSON.")

        pdf_path = select_json(
            title="Select the Matching PDF Extraction",
            initial_directory="output/pdfs"
        )

        if not pdf_path:
            print("No PDF extraction selected.")
            return

        pdf_data = load_json(pdf_path)

        if not isinstance(pdf_data, dict):
            raise ValueError(
                "The selected PDF JSON is invalid."
            )

        if pdf_data.get("source_type") != "pdf":
            raise ValueError(
                "The selected JSON is not a PDF extraction result."
            )

        # Step 3: Generate text chunks.
        print("\nGenerating research chunks...")

        chunks_data = process_pdf_extraction(
            pdf_data,
            max_chars=1200,
            overlap_chars=150
        )

        print("\n========== CHUNK PROCESSING RESULTS ==========")

        print("Source:", chunks_data["source_file"])
        print("Pages:", chunks_data["page_count"])
        print("Paragraphs:", chunks_data["total_paragraphs"])
        print("Chunks:", chunks_data["total_chunks"])

        # Step 4: Link chunks to the approved profile.
        print("\nLinking chunks to the research profile...")

        package = build_chunk_package(
            profile,
            pdf_data,
            chunks_data
        )

        # Step 5: Save the raw chunks.
        source_base = Path(pdf_path).stem

        chunks_output = save_json(
            chunks_data,
            "output/chunks",
            f"{source_base}_chunks.json"
        )

        # Step 6: Save the linked research package.
        package_output = save_json(
            package,
            "output/chunks",
            f"{source_base}_research_package.json"
        )

        # Step 7: Display the package summary.
        print("\n========== LINKED RESEARCH PACKAGE ==========")

        print("Research title:", profile["research"].get("title"))
        print("Profile status:", package["profile_review"]["status"])
        print("Source PDF:", package["source"]["file_name"])

        print("\nSection chunk counts:")

        for name, section in package["sections"].items():

            print(
                f"- {name.replace('_', ' ').title()}: "
                f"{section['chunk_count']} chunks"
            )

        print(
            "\nUnclassified chunks:",
            package["chunk_processing"]["unclassified_chunks"]
        )

        print(
            "Unmapped chunks:",
            package["chunk_processing"]["unmapped_chunks"]
        )

        print("\nValidation:")

        for key, value in package["validation"].items():

            if key != "warnings":
                print(f"- {key}: {value}")

        if package["validation"]["warnings"]:

            print("\nWarnings:")

            for warning in package["validation"]["warnings"]:
                print(f"- {warning}")

        print("\n========== OUTPUT FILES ==========")
        print("Chunks:", chunks_output)
        print("Research package:", package_output)

        print("\nChunk processing and profile linking completed.")

    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
        KeyError
    ) as error:

        print(f"\nChunk processing failed: {error}")


# ---------------------------------------------------------
# MAIN MENU
# ---------------------------------------------------------

def main():

    while True:

        print("\n")
        print("=" * 45)
        print("              RESEARCHLENS")
        print("=" * 45)

        print("1. Extract Website Article")
        print("2. Extract PDF Research Paper")
        print("3. Create Research Profile")
        print("4. Review Existing Research Profile")
        print("5. Generate Research Chunks and Link Profile")
        print("6. Exit")

        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            run_website_scraper()

        elif choice == "2":
            run_pdf_extractor()

        elif choice == "3":
            run_profile_creator()

        elif choice == "4":
            run_existing_profile_editor()

        elif choice == "5":
            run_chunk_pipeline()

        elif choice == "6":
            print("\nExiting ResearchLens.")
            break

        else:
            print("\nInvalid selection. Please try again.")


if __name__ == "__main__":
    main()
