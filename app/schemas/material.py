from datetime import datetime
from pydantic import BaseModel


class MaterialCreate(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None
    supplier: str | None = None
    sku: str | None = None
    unit: str = "ea"
    default_price: float


class MaterialUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    supplier: str | None = None
    sku: str | None = None
    unit: str | None = None
    default_price: float | None = None
    is_active: bool | None = None


class MaterialOut(BaseModel):
    id: int
    name: str
    description: str | None
    category: str | None
    supplier: str | None
    sku: str | None
    unit: str
    default_price: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
