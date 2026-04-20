import pytesseract
from PIL import Image
import pdfplumber
import json
import sys
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\22600004\Downloads\Auto-Doc\tools\tesseract\tesseract.exe"
def extract_text_from_image(image_path):
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang="fra")  # ou "eng"
    return text

def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def main(file_path):
    if file_path.lower().endswith(".pdf"):
        text = extract_text_from_pdf(file_path)
    else:
        text = extract_text_from_image(file_path)

    output = {"extracted_text": text}
    print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ocr_app.py <file_path>")
    else:
        main(sys.argv[1])
