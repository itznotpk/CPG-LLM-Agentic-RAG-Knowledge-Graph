import fitz
import sys

doc = fitz.open("CPG Management of Heart Failure (5th Edition).pdf")
for page_num in [128, 129]: # pages 129 and 130 in reader (PDFs are 0-indexed, so 128 is physical page 129)
    page = doc.load_page(page_num)
    pix = page.get_pixmap(dpi=150)
    pix.save(f"page_{page_num+1}.png")
print("Saved pages as images.")
