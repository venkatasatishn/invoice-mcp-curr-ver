from __future__ import annotations

import json
from typing import Dict, Any, List, Tuple

from openai import OpenAI
from openai.lib._pydantic import to_strict_json_schema

from app.core.schema import CanonicalInvoice


client = OpenAI()
CANONICAL_SCHEMA = to_strict_json_schema(CanonicalInvoice)

SYSTEM_INSTRUCTIONS = """
You extract invoice data and return ONLY valid JSON per the provided schema.

Rules:
- If unknown, use null.
- Dates must be YYYY-MM-DD when possible.
- Currency: output ISO 4217 if clear; otherwise null.
- Extract payment.due_date and payment.amount_due if present (Balance Due / Amount Due).
- Extract line items with quantity, unit_price, amount, tax_rate and tax_amount when available.
- If you see buyer endpoint details useful for Peppol, populate buyer.endpoint.id and buyer.endpoint.scheme_id.
"""


def extract_canonical_from_pdf(pdf_bytes: bytes) -> Tuple[Dict[str, Any], List[str]]:
    """
    Extract canonical invoice JSON from PDF using OpenAI.

    This version uploads the PDF first and then references it by file_id.
    That is more reliable than sending inline file_data for PDFs.
    """
    warnings: List[str] = []

    uploaded = client.files.create(
        file=("invoice.pdf", pdf_bytes, "application/pdf"),
        purpose="user_data",
    )

    resp = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": SYSTEM_INSTRUCTIONS,
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "file_id": uploaded.id,
                    },
                    {
                        "type": "input_text",
                        "text": "Extract this invoice into the canonical JSON schema.",
                    },
                ],
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "CanonicalInvoice",
                "schema": CANONICAL_SCHEMA,
                "strict": True,
            }
        },
    )

    out = resp.output_text
    if isinstance(out, str):
        out = json.loads(out)

    return out, warnings
