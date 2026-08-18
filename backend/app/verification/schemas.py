import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class VerificationResultOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    document_category: str
    check_type: str
    registry_table: str | None
    status: str
    discrepancy_details: dict[str, Any] | None
    created_at: datetime


class VerifyApplicationResponse(BaseModel):
    application_id: uuid.UUID
    results: list[VerificationResultOut]
