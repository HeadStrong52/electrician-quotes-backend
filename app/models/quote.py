import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Text, ForeignKey, Numeric, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class QuoteStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    APPROVED = "approved"
    DECLINED = "declined"
    INVOICED = "invoiced"
    PAID = "paid"


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    status: Mapped[QuoteStatus] = mapped_column(
        Enum(QuoteStatus), default=QuoteStatus.DRAFT
    )

    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cached totals (recalculated on save)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    gst: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    # GST rate as a decimal, e.g. 0.10 for 10%
    gst_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0.10)

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    client: Mapped["Client"] = relationship(back_populates="quotes")
    created_by: Mapped["User"] = relationship(back_populates="quotes")
    line_items: Mapped[list["LineItem"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", order_by="LineItem.sort_order"
    )

    @property
    def client_name(self) -> str:
        return self.client.name if self.client else ""
