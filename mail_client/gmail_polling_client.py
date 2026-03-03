from __future__ import annotations
import base64
import os
import re
import sqlite3
import time
from typing import List, Tuple

import requests
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

MCP_CONVERT_URL = os.getenv("MCP_CONVERT_URL", "http://localhost:8000/convert")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "60"))

KEYWORDS = ["invoice", "tax invoice", "bill", "payment due", "amount due", "balance due"]

def looks_like_invoice(subject: str, snippet: str) -> bool:
    t = f"{subject}\n{snippet}".lower()
    return any(k in t for k in KEYWORDS)

def init_db(path="mail_client/state.db"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS processed (msg_id TEXT PRIMARY KEY)")
    conn.commit()
    return conn

def is_processed(conn, msg_id: str) -> bool:
    cur = conn.execute("SELECT 1 FROM processed WHERE msg_id=?", (msg_id,))
    return cur.fetchone() is not None

def mark_processed(conn, msg_id: str):
    conn.execute("INSERT OR IGNORE INTO processed(msg_id) VALUES(?)", (msg_id,))
    conn.commit()

def get_gmail(creds: Credentials):
    return build("gmail", "v1", credentials=creds)

def fetch_pdfs(gmail, msg_id: str) -> List[Tuple[str, bytes]]:
    msg = gmail.users().messages().get(userId="me", id=msg_id, format="full").execute()
    payload = msg.get("payload", {})
    parts = payload.get("parts", [])
    out: List[Tuple[str, bytes]] = []

    def walk(ps):
        for p in ps:
            if p.get("parts"):
                walk(p["parts"])
            mime = p.get("mimeType", "")
            filename = p.get("filename", "")
            body = p.get("body", {})
            if mime == "application/pdf" and body.get("attachmentId"):
                att = gmail.users().messages().attachments().get(
                    userId="me", messageId=msg_id, id=body["attachmentId"]
                ).execute()
                data = base64.urlsafe_b64decode(att["data"].encode("utf-8"))
                out.append((filename or "attachment.pdf", data))

    walk(parts)
    return out

def mark_as_read(gmail, msg_id: str):
    gmail.users().messages().modify(userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}).execute()

def call_convert(pdf_bytes: bytes) -> dict:
    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    r = requests.post(
        MCP_CONVERT_URL,
        json={"pdf_base64": pdf_b64, "return_raw_text": False, "force_local_ocr": False, "ubl_format": "xml"},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()

def run(creds: Credentials):
    gmail = get_gmail(creds)
    conn = init_db()

    while True:
        res = gmail.users().messages().list(userId="me", q="is:unread has:attachment").execute()
        for m in res.get("messages", []):
            msg_id = m["id"]
            if is_processed(conn, msg_id):
                continue

            meta = gmail.users().messages().get(userId="me", id=msg_id, format="metadata").execute()
            headers = {h["name"].lower(): h["value"] for h in meta["payload"].get("headers", [])}
            subject = headers.get("subject", "")
            snippet = meta.get("snippet", "")

            if not looks_like_invoice(subject, snippet):
                mark_processed(conn, msg_id)
                continue

            pdfs = fetch_pdfs(gmail, msg_id)
            if not pdfs:
                mark_processed(conn, msg_id)
                continue

            all_ok = True
            for filename, pdf_bytes in pdfs:
                try:
                    out = call_convert(pdf_bytes)
                    if not out.get("ok"):
                        all_ok = False
                        print("Convert failed:", filename, out)
                    else:
                        invno = out["result"]["custom_invoice_json"].get("invoice_number")
                        print("Processed:", filename, "invoice_number:", invno)
                except Exception as e:
                    all_ok = False
                    print("Exception processing", filename, ":", str(e))

            # Only mark email read if everything succeeded
            if all_ok:
                mark_as_read(gmail, msg_id)

            mark_processed(conn, msg_id)

        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    # Load Credentials via OAuth (not shown). You likely already have this in your environment.
    # creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/gmail.modify"])
    # run(creds)
    raise SystemExit("Provide Gmail OAuth creds and call run(creds).")
