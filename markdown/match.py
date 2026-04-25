import fitz

doc = fitz.open("CPG Management of Heart Failure (5th Edition).pdf")
for page_num in [128, 129]:
    print(f"--- PAGE {page_num+1} ---")
    page = doc.load_page(page_num)
    blocks = page.get_text("dict")["blocks"]

    grades = []
    texts = []
    for b in blocks:
        if "lines" in b:
            line_text = []
            min_y = 9999
            for l in b["lines"]:
                for s in l["spans"]:
                    text = s["text"].strip()
                    if not text: continue
                    x0, y0, x1, y1 = s["bbox"]
                    if x0 < 80 and ("," in text or len(text) <= 5) and any(c in text for c in "IVABCa,"):
                        grades.append((y0, text))
                    elif x0 >= 80:
                        line_text.append(text)
                        min_y = min(min_y, y0)
            if line_text:
                texts.append((min_y, " ".join(line_text)))

    grades.sort(key=lambda x: x[0])
    texts.sort(key=lambda x: x[0])

    for gy, grade in grades:
        print(f"\nGRADE: {grade} (y={gy})")
        for ty, text in texts:
            if abs(ty - gy) < 25:
                print(f"  T: {text}")
