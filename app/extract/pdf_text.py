import io
import re
import pdfplumber

def extract_text(pdf_bytes: bytes) -> tuple[str, int]:
    chunks = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for p in pdf.pages:
            chunks.append(p.extract_text() or "")
        return "\n".join(chunks).strip(), len(pdf.pages)

def looks_scanned(text: str) -> bool:
    return len(re.sub(r"\s+", "", text)) < 80
