from __future__ import annotations
import base64
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.core.schema import CanonicalInvoice
from app.core.currency import normalize_currency
from app.core.errors import AppError, new_trace_id
from app.core.peppol import build_peppol_ubl_invoice

from app.extract.pdf_text import extract_text, looks_scanned
from app.extract.ocr import ocr_pdf_bytes
from app.extract.openai_map import extract_canonical_from_pdf


def is_pdf_bytes(b: bytes) -> bool:
    return b[:5] == b"%PDF-"

def invoice_pdf_to_standard(
    pdf_base64: str,
    return_raw_text: bool = False,
    force_local_ocr: bool = False,
    ubl_format: str = "xml",
) -> Dict[str, Any]:
    trace_id = new_trace_id()

    try:
        pdf_bytes = base64.b64decode(pdf_base64, validate=True)
    except Exception:
        raise AppError(
            code="INVALID_BASE64",
            message="pdf_base64 is not valid base64.",
            details={"trace_id": trace_id},
            http_status=400,
        )

    if not is_pdf_bytes(pdf_bytes):
        raise AppError(
            code="INVALID_PDF",
            message="Decoded bytes are not a PDF (missing %PDF- header).",
            details={"trace_id": trace_id},
            http_status=400,
        )

    warnings: List[str] = []
    validation_errors: List[str] = []
    ocr_used = False

    # Extract raw text (for currency/due heuristics + debugging)
    try:
        raw_text, pages = extract_text(pdf_bytes)
    except Exception as e:
        raise AppError(
            code="PDF_PARSE_FAILED",
            message="Failed to parse PDF for text extraction.",
            details={"trace_id": trace_id, "reason": str(e)},
            http_status=400,
        )

    # Optional local OCR if scanned
    if force_local_ocr or looks_scanned(raw_text):
        try:
            raw_text = ocr_pdf_bytes(pdf_bytes)
            ocr_used = True
        except Exception as e:
            warnings.append(f"Local OCR failed; continuing with model PDF vision. Reason: {e}")

    # OpenAI extraction (uses PDF vision)
    try:
        canonical_dict, openai_warnings = extract_canonical_from_pdf(pdf_bytes)
        warnings.extend(openai_warnings)
    except Exception as e:
        raise AppError(
            code="OPENAI_EXTRACTION_FAILED",
            message="OpenAI extraction failed.",
            details={"trace_id": trace_id, "reason": str(e)},
            http_status=502,
        )

    # Validate + normalize into CanonicalInvoice
    try:
        canonical_obj = CanonicalInvoice.model_validate(canonical_dict)
        canonical = canonical_obj.model_dump()
    except ValidationError as e:
        validation_errors.append(str(e))
        canonical = canonical_dict  # best-effort

    # Fill meta
    canonical.setdefault("meta", {})
    canonical["meta"].update({"source": "pdf", "pages": pages, "ocr_used": ocr_used, "trace_id": trace_id})

    # Currency normalization
    canonical["currency"] = normalize_currency(raw_text, canonical.get("currency"))

    # Due amount fallback: if amount_due missing, use grand_total
    payment = canonical.get("payment") or {}
    totals = canonical.get("totals") or {}
    if payment.get("amount_due") is None and totals.get("grand_total") is not None:
        payment["amount_due"] = totals["grand_total"]
        canonical["payment"] = payment

    # Buyer endpoint defaults (your org) from env, if missing
    import os
    buyer = canonical.get("buyer") or {}
    be = (buyer.get("endpoint") or {})
    if not be.get("id") and os.getenv("BUYER_ENDPOINT_ID"):
        be["id"] = os.getenv("BUYER_ENDPOINT_ID")
    if not be.get("scheme_id") and os.getenv("BUYER_ENDPOINT_SCHEME"):
        be["scheme_id"] = os.getenv("BUYER_ENDPOINT_SCHEME")
    buyer["endpoint"] = be
    canonical["buyer"] = buyer

    # Peppol XML (fail with clear error if required fields missing)
    try:
        peppol_xml, peppol_warnings = build_peppol_ubl_invoice(canonical)
        warnings.extend(peppol_warnings)
    except Exception as e:
        raise AppError(
            code="PEPPOL_XML_FAILED",
            message="Failed to generate Peppol BIS Billing 3.0 UBL Invoice XML.",
            details={"trace_id": trace_id, "reason": str(e)},
            http_status=422,
        )

    result = {
        "custom_invoice_json": canonical,
        "peppol_ubl_xml": peppol_xml,
        "warnings": warnings,
        "validation_errors": validation_errors,
        "ocr_used": ocr_used,
    }
    if return_raw_text:
        result["raw_text"] = raw_text

    return {"ok": True, "result": result}
