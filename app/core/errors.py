from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
import uuid

@dataclass
class AppError(Exception):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    http_status: int = 400

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details or {},
            },
        }

def new_trace_id() -> str:
    return uuid.uuid4().hex
