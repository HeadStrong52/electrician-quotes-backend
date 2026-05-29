from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
import re


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    business_name: str
    password: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name is required")
        return v.strip()

    @field_validator("business_name")
    @classmethod
    def business_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Business name is required")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        errors = []
        if len(v) < 8:
            errors.append("at least 8 characters")
        if not re.search(r"[A-Z]", v):
            errors.append("one uppercase letter")
        if not re.search(r"[a-z]", v):
            errors.append("one lowercase letter")
        if not re.search(r"\d", v):
            errors.append("one number")
        if errors:
            raise ValueError(f"Password must contain {', '.join(errors)}")
        return v


class CompanyUpdate(BaseModel):
    name: str | None = None
    business_name: str | None = None
    phone: str | None = None
    address: str | None = None
    rec_licence: str | None = None
    logo: str | None = None  # base64 data URI, or "" to clear


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    business_name: str | None
    is_active: bool
    is_admin: bool
    created_at: datetime
    phone: str | None
    address: str | None
    rec_licence: str | None
    logo: str | None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: int | None = None
