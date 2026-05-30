from datetime import datetime
from pydantic import BaseModel
from app.models.quote import QuoteStatus
from app.models.line_item import LineItemType


class LineItemCreate(BaseModel):
    type: LineItemType
    description: str
    quantity: float = 1.0
    unit: str = "ea"
    unit_price: float
    sort_order: int = 0
    material_id: int | None = None


class LineItemUpdate(BaseModel):
    type: LineItemType | None = None
    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    sort_order: int | None = None


class LineItemOut(BaseModel):
    id: int
    type: LineItemType
    description: str
    quantity: float
    unit: str
    unit_price: float
    total: float
    sort_order: int
    material_id: int | None

    model_config = {"from_attributes": True}


class QuoteCreate(BaseModel):
    client_id: int
    title: str
    description: str | None = None
    site_address: str | None = None
    notes: str | None = None
    gst_rate: float = 0.10
    valid_until: datetime | None = None
    line_items: list[LineItemCreate] = []


class QuoteUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    site_address: str | None = None
    notes: str | None = None
    gst_rate: float | None = None
    valid_until: datetime | None = None
    status: QuoteStatus | None = None
    line_items: list[LineItemCreate] | None = None


class QuoteSummary(BaseModel):
    id: int
    quote_number: str
    title: str
    status: QuoteStatus
    client_id: int
    client_name: str
    site_address: str | None
    subtotal: float
    gst: float
    total: float
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuoteOut(BaseModel):
    id: int
    quote_number: str
    title: str
    description: str | None
    site_address: str | None
    notes: str | None
    status: QuoteStatus
    client_id: int
    client_name: str
    created_by_id: int
    is_archived: bool
    subtotal: float
    gst: float
    total: float
    gst_rate: float
    valid_until: datetime | None
    sent_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    line_items: list[LineItemOut]

    model_config = {"from_attributes": True}
