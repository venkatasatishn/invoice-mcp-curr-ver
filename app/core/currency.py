import re
from typing import Optional

SYMBOL_TO_ISO = {
    "$": "USD",
    "₹": "INR",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",  # could be CNY/JPY; we keep JPY unless code found
}

ISO_RE = re.compile(r"\b([A-Z]{3})\b")

def normalize_currency(raw_text: str, model_currency: Optional[str]) -> Optional[str]:
    # If model already produced a 3-letter code, accept it.
    if model_currency and re.fullmatch(r"[A-Z]{3}", model_currency.strip().upper()):
        return model_currency.strip().upper()

    t = raw_text or ""

    # Prefer explicit 3-letter codes found in text
    m = ISO_RE.search(t.upper())
    if m:
        return m.group(1)

    # Otherwise infer from symbol
    for sym, iso in SYMBOL_TO_ISO.items():
        if sym in t:
            return iso

    return None
