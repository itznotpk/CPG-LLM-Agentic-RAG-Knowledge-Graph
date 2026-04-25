import pypdf
import sys

reader = pypdf.PdfReader("CPG Management of Heart Failure (5th Edition).pdf")
with open("out.txt", "w", encoding="utf-8") as f:
    for i in range(len(reader.pages)):
        page = reader.pages[i]
        text = page.extract_text()
        if "14.4 " in text or "14.4.1" in text or "14.5" in text or "CARDIO-ONCOLOGY" in text or "Pacing Induced" in text:
            f.write(f"--- PAGE {i+1} ---\n")
            f.write(text + "\n")
