
import json
import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

from scraper.pdf_extractor import extract_pdf


def generate_filename(filename):
    """Generate a filesystem-safe filename."""

    filename = Path(filename).stem

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        filename.lower()
    ).strip("-")

    return slug or "document"


def save_pdf_result(result):
    """Save extracted PDF information as JSON."""

    output_dir = Path("output/pdfs")
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = generate_filename(result["file_name"])
    output_file = output_dir / f"{base_name}.json"

    counter = 2

    while output_file.exists():
        output_file = output_dir / f"{base_name}-{counter}.json"
        counter += 1

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(f"\nPDF extraction saved to: {output_file}")


def select_pdf():
    """Open a file dialog for PDF selection."""

    root = tk.Tk()
    root.withdraw()

    root.attributes("-topmost", True)

    pdf_path = filedialog.askopenfilename(
        title="Select a Research Paper",
        initialdir=str(Path("input/pdfs").resolve()),
        filetypes=[
            ("PDF Documents", "*.pdf"),
            ("All Files", "*.*")
        ]
    )

    root.destroy()

    return pdf_path


def main():
    print("Opening PDF file selector...")

    pdf_path = select_pdf()

    if not pdf_path:
        print("No PDF selected. Operation cancelled.")
        return

    try:
        result = extract_pdf(pdf_path)

        metadata = result["metadata"]

        print("\n========== PDF INFORMATION ==========")

        print(f"File: {result['file_name']}")
        print(f"Title: {metadata['title']}")
        print("\nAuthors:")
        if metadata["authors"]:
            for index, author in enumerate(metadata["authors"], start=1):
                print(f"{index}. {author}")
        else:
            print("No authors detected.")
        print(f"Subject: {metadata['subject']}")
        print(f"Pages: {result['page_count']}")
        print(f"Pages with text: {result['pages_with_text']}")
        print(f"Total characters: {result['total_characters']}")

        print("\n========== EXTRACTION RESULT ==========")

        if result["extraction_status"] == "no_text_detected":
            print("No selectable text detected.")
            print("This PDF may be scanned or image-based.")
        else:
            print(result["text"][:2000])
            print("\nShowing first 2,000 characters.")

        save_pdf_result(result)

    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"\nPDF extraction failed: {error}")


if __name__ == "__main__":
    main()
