# -*- coding: utf-8 -*-
import fitz  # PyMuPDF
import os
import re
import sys

# Windows 콘솔에서 유니코드 출력 허용
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PDF_DIR = r"C:\Users\cho_b\Documents\이&최 습식 실리콘 논문"
OUTPUT_FILE = os.path.join(PDF_DIR, "merged_corpus.txt")

STOP_PATTERNS = re.compile(r"^\s*(references|acknowledgements|acknowledgments)\b", re.IGNORECASE)


def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    pages_text = []

    for page in doc:
        text = page.get_text()
        if STOP_PATTERNS.match(text.strip()):
            break
        pages_text.append(text)

    doc.close()
    return "\n".join(pages_text)


def main():
    pdf_files = sorted(
        f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")
    )

    if not pdf_files:
        print("No PDF files found.")
        return

    print("Processing {} PDF file(s)...\n".format(len(pdf_files)))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for filename in pdf_files:
            pdf_path = os.path.join(PDF_DIR, filename)
            print("  [{}]".format(filename))
            try:
                text = extract_text_from_pdf(pdf_path)
                out.write("=" * 80 + "\n")
                out.write("[SOURCE: {}]\n".format(filename))
                out.write("=" * 80 + "\n")
                out.write(text)
                out.write("\n\n")
            except Exception as e:
                print("    ERROR: {}".format(e))

    print("\nDone! Output: {}".format(OUTPUT_FILE))


if __name__ == "__main__":
    main()
