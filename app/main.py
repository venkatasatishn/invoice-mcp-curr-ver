from fastapi import FastAPI
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP

from app.tools import invoice_pdf_to_standard
from app.core.errors import AppError

mcp = FastMCP("invoice-standardizer", stateless_http=True)

@mcp.tool()
def invoice_pdf_to_standard_tool(
    pdf_base64: str,
    return_raw_text: bool = False,
    force_local_ocr: bool = False,
    ubl_format: str = "xml",
):
    return invoice_pdf_to_standard(
        pdf_base64=pdf_base64,
        return_raw_text=return_raw_text,
        force_local_ocr=force_local_ocr,
        ubl_format=ubl_format,
    )

app = FastAPI()
app.mount("/mcp", mcp.streamable_http_app())

@app.get("/health")
def health():
    return {"ok": True}

# Optional REST endpoint (handy for testing & mail client)
from pydantic import BaseModel

class ConvertRequest(BaseModel):
    pdf_base64: str
    return_raw_text: bool = False
    force_local_ocr: bool = False
    ubl_format: str = "xml"

@app.post("/convert")
def convert(req: ConvertRequest):
    return invoice_pdf_to_standard(
        pdf_base64=req.pdf_base64,
        return_raw_text=req.return_raw_text,
        force_local_ocr=req.force_local_ocr,
        ubl_format=req.ubl_format,
    )

@app.exception_handler(AppError)
def app_error_handler(_, exc: AppError):
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())

@app.exception_handler(Exception)
def unhandled_error(_, exc: Exception):
    # Production-safe generic error, but still returns a trace_id-ish handle
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal Server Error", "details": {"reason": str(exc)}}},
    )
