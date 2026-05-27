import enum
from sqlalchemy import String, ForeignKey, Numeric, Integer, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class LineItemType(str, enum.Enum):
    LABOUR = "labour"
    MATERIAL = "material"
    OTHER = "other"


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"))
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("materials.id"), nullable=True
    )

    type: Mapped[LineItemType] = mapped_column(Enum(LineItemType))
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), default=1)
    unit: Mapped[str] = mapped_column(String(50), default="ea")
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))
    total: Mapped[float] = mapped_column(Numeric(10, 2))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    quote: Mapped["Quote"] = relationship(back_populates="line_items")
    material: Mapped["Material | None"] = relationship()
