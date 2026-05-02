from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List


class Attachment(BaseModel):
    filename: str
    content_type: str   # z.B. "application/pdf" oder "image/png"
    data: str           # Base64-kodierter Dateiinhalt

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if "/" not in v:
            raise ValueError("content_type muss im Format 'typ/subtyp' sein, z.B. 'application/pdf'")
        return v


class EmailRequest(BaseModel):
    to: List[EmailStr]
    cc: Optional[List[EmailStr]] = []
    bcc: Optional[List[EmailStr]] = []
    subject: str
    from_name: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    attachments: Optional[List[Attachment]] = []

    @field_validator("to")
    @classmethod
    def to_not_empty(cls, v: List[EmailStr]) -> List[EmailStr]:
        if not v:
            raise ValueError("Mindestens ein Empfänger in 'to' erforderlich")
        return v

    @field_validator("body_text", "body_html")
    @classmethod
    def at_least_one_body(cls, v: Optional[str]) -> Optional[str]:
        return v

    def has_body(self) -> bool:
        return bool(self.body_text or self.body_html)


class EmailResponse(BaseModel):
    success: bool
    detail: str
