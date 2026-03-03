from __future__ import annotations
from typing import Any, Dict, List, Tuple
from lxml import etree

PEPPOL_CUSTOMIZATION_ID = "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
PEPPOL_PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"

NSMAP = {
    None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}

def _missing(inv: Dict[str, Any]) -> List[str]:
    miss = []
    if not inv.get("invoice_number"): miss.append("invoice_number")
    if not inv.get("invoice_date"): miss.append("invoice_date")
    if not inv.get("currency"): miss.append("currency")
    seller = (inv.get("seller") or {})
    buyer = (inv.get("buyer") or {})
    if not seller.get("name"): miss.append("seller.name")
    if not buyer.get("name"): miss.append("buyer.name")
    totals = inv.get("totals") or {}
    if totals.get("grand_total") is None: miss.append("totals.grand_total")

    # Peppol endpoints are mandatory in the Peppol syntax model; if you can’t extract,
    # you can supply defaults for BUYER via env/config. We enforce buyer endpoint.
    be = (buyer.get("endpoint") or {})
    if not be.get("id"): miss.append("buyer.endpoint.id")
    if not be.get("scheme_id"): miss.append("buyer.endpoint.scheme_id")
    return miss

def build_peppol_ubl_invoice(inv: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    Returns (xml_string, warnings)
    """
    warnings: List[str] = []
    missing = _missing(inv)
    if missing:
        # We fail fast because you asked for Peppol-compliant XML.
        # (In a later iteration we can return a draft XML plus errors.)
        raise ValueError(f"Missing required fields for Peppol UBL Invoice: {missing}")

    root = etree.Element("Invoice", nsmap=NSMAP)
    cbc = "{%s}" % NSMAP["cbc"]
    cac = "{%s}" % NSMAP["cac"]

    def add(tag: str, text: str | None):
        el = etree.SubElement(root, cbc + tag)
        el.text = text or ""
        return el

    add("CustomizationID", PEPPOL_CUSTOMIZATION_ID)
    add("ProfileID", PEPPOL_PROFILE_ID)
    add("ID", inv["invoice_number"])
    add("IssueDate", inv["invoice_date"])
    add("InvoiceTypeCode", "380")  # commercial invoice
    add("DocumentCurrencyCode", inv["currency"])

    # Optional due date
    due_date = (inv.get("payment") or {}).get("due_date")
    if due_date:
        add("DueDate", due_date)

    # Parties
    seller = inv["seller"]
    buyer = inv["buyer"]

    sup = etree.SubElement(root, cac + "AccountingSupplierParty")
    sup_party = etree.SubElement(sup, cac + "Party")
    etree.SubElement(etree.SubElement(sup_party, cac + "PartyName"), cbc + "Name").text = seller["name"]

    cust = etree.SubElement(root, cac + "AccountingCustomerParty")
    cust_party = etree.SubElement(cust, cac + "Party")
    be = buyer["endpoint"]
    endpoint = etree.SubElement(cust_party, cbc + "EndpointID")
    endpoint.text = be["id"]
    endpoint.attrib["schemeID"] = be["scheme_id"]
    etree.SubElement(etree.SubElement(cust_party, cac + "PartyName"), cbc + "Name").text = buyer["name"]

    # Monetary totals
    totals = inv["totals"]
    currency = inv["currency"]

    legal = etree.SubElement(root, cac + "LegalMonetaryTotal")
    def amt(tag: str, value: float | None):
        el = etree.SubElement(legal, cbc + tag)
        el.attrib["currencyID"] = currency
        el.text = "" if value is None else f"{value:.2f}"
        return el

    amt("TaxExclusiveAmount", totals.get("sub_total"))
    amt("TaxInclusiveAmount", totals.get("grand_total"))

    # Amount due for payment (BT-115) is typically cbc:PayableAmount under LegalMonetaryTotal
    amount_due = (inv.get("payment") or {}).get("amount_due")
    if amount_due is not None:
        el = etree.SubElement(legal, cbc + "PayableAmount")
        el.attrib["currencyID"] = currency
        el.text = f"{amount_due:.2f}"

    # Lines (minimal)
    for idx, li in enumerate(inv.get("line_items") or [], start=1):
        line = etree.SubElement(root, cac + "InvoiceLine")
        etree.SubElement(line, cbc + "ID").text = str(idx)

        q = etree.SubElement(line, cbc + "InvoicedQuantity")
        q.text = "" if li.get("quantity") is None else str(li["quantity"])

        lea = etree.SubElement(line, cbc + "LineExtensionAmount")
        lea.attrib["currencyID"] = currency
        lea.text = "" if li.get("amount") is None else f"{li['amount']:.2f}"

        item = etree.SubElement(line, cac + "Item")
        etree.SubElement(item, cbc + "Description").text = li.get("description") or ""

    xml = etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return xml, warnings
