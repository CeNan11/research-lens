
import json
import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

from scraper.web_scraper import scrape_article
from scraper.pdf_extractor import extract_pdf


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
        json.dump(data, file, indent=4, ensure_ascii=False)

    print(f"\nSaved to: {output_file}")


def select_pdf():
    """Open a PDF file selector."""

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        return filedialog.askopenfilename(
            title="Select a Research Paper",
            initialdir=str(Path("input/pdfs").resolve()),
            filetypes=[
                ("PDF Documents", "*.pdf"),
                ("All Files", "*.*")
            ]
        )
    finally:
        root.destroy()


def run_website_scraper():
    """Handle website article extraction."""

    url = input("\nEnter article URL: ").strip()

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


def main():
    print("\n========== RESEARCHLENS ==========")
    print("1. Extract Website Article")
    print("2. Extract PDF Research Paper")
    print("3. Exit")

    choice = input("\nSelect an option: ").strip()

    if choice == "1":
        run_website_scraper()

    elif choice == "2":
        run_pdf_extractor()

    elif choice == "3":
        print("Exiting ResearchLens.")

    else:
        print("Invalid selection.")


if __name__ == "__main__":
    main()
