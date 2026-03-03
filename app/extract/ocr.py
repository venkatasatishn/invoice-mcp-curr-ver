import io
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

def ocr_pdf_bytes(pdf_bytes: bytes, dpi: int = 250) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    parts = []
    for page in doc:
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        parts.append(pytesseract.image_to_string(img))
    return "\n".join(parts).strip()
