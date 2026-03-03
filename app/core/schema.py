from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field

class Endpoint(BaseModel):
    id: Optional[str] = None
    scheme_id: Optional[str] = None  # e.g. "0192"

class Party(BaseModel):
    name: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    endpoint: Endpoint = Field(default_factory=Endpoint)

class LineItem(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    hsn_sac: Optional[str] = None

class Totals(BaseModel):
    sub_total: Optional[float] = None
    tax_total: Optional[float] = None
    grand_total: Optional[float] = None

class Payment(BaseModel):
    due_date: Optional[str] = None        # YYYY-MM-DD
    amount_due: Optional[float] = None    # Balance due / Amount due
    terms: Optional[str] = None           # free text if present

class Meta(BaseModel):
    source: Optional[str] = None
    pages: Optional[int] = None
    ocr_used: Optional[bool] = None

class CanonicalInvoice(BaseModel):
    schema_version: str = "invoice-json-v1"
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    currency: Optional[str] = None  # ISO 4217
    seller: Party = Field(default_factory=Party)
    buyer: Party = Field(default_factory=Party)
    payment: Payment = Field(default_factory=Payment)
    line_items: List[LineItem] = Field(default_factory=list)
    totals: Totals = Field(default_factory=Totals)
    meta: Meta = Field(default_factory=Meta)
