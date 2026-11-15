
import pymupdf
import tkinter as tk
from tkinter import filedialog
from pathlib import Path


root = tk.Tk()
root.withdraw()

pdf_path = filedialog.askopenfilename(
    title="Select a PDF to create a scanned test copy",
    filetypes=[("PDF Documents", "*.pdf")]
)

root.destroy()

if not pdf_path:
    print("No PDF selected.")
    raise SystemExit

output_dir = Path("input/pdfs")
output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / "ocr-test-scanned.pdf"

with pymupdf.open(pdf_path) as source:
    scanned = pymupdf.open()

    # Render the first two pages as images.
    for index in range(min(2, len(source))):
        page = source[index]

        pixmap = page.get_pixmap(
            dpi=150,
            colorspace=pymupdf.csRGB,
            alpha=False
        )

        new_page = scanned.new_page(
            width=page.rect.width,
            height=page.rect.height
        )

        new_page.insert_image(
            new_page.rect,
            pixmap=pixmap
        )

    scanned.save(output_path)
    scanned.close()

print(f"Scanned test PDF created: {output_path}")
