from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models.quote import Quote, QuoteStatus
from app.models.line_item import LineItem
from app.models.client import Client
from app.models.user import User
from app.schemas.quote import QuoteCreate, QuoteUpdate, QuoteOut, QuoteSummary
from app.auth import get_current_user
from app.pdf import generate_quote_pdf
from app.email_sender import send_quote_email
from app.config import settings

router = APIRouter(prefix="/quotes", tags=["quotes"])


def _next_quote_number(db: Session) -> str:
    count = db.query(Quote).count() + 1
    year = datetime.utcnow().year
    return f"Q{year}-{count:04d}"


def _recalculate(quote: Quote):
    subtotal = sum(float(item.total) for item in quote.line_items)
    gst = round(subtotal * float(quote.gst_rate), 2)
    quote.subtotal = round(subtotal, 2)
    quote.gst = gst
    quote.total = round(subtotal + gst, 2)


def _apply_line_items(quote: Quote, items_data: list, db: Session):
    for item in quote.line_items:
        db.delete(item)
    quote.line_items = []
    for i, item_data in enumerate(items_data):
        total = round(float(item_data.quantity) * float(item_data.unit_price), 2)
        line = LineItem(
            quote_id=quote.id,
            type=item_data.type,
            description=item_data.description,
            quantity=item_data.quantity,
            unit=item_data.unit,
            unit_price=item_data.unit_price,
            total=total,
            sort_order=item_data.sort_order if item_data.sort_order else i,
            material_id=item_data.material_id,
        )
        db.add(line)
        quote.line_items.append(line)


@router.get("", response_model=list[QuoteSummary])
def list_quotes(
    status: QuoteStatus | None = None,
    client_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Quote).options(joinedload(Quote.client))
    if status:
        query = query.filter(Quote.status == status)
    if client_id:
        query = query.filter(Quote.client_id == client_id)
    quotes = query.order_by(Quote.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for q in quotes:
        result.append(QuoteSummary(
            id=q.id,
            quote_number=q.quote_number,
            title=q.title,
            status=q.status,
            client_id=q.client_id,
            client_name=q.client.name,
            subtotal=float(q.subtotal),
            gst=float(q.gst),
            total=float(q.total),
            created_at=q.created_at,
            updated_at=q.updated_at,
        ))
    return result


@router.post("", response_model=QuoteOut, status_code=201)
def create_quote(
    body: QuoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not db.get(Client, body.client_id):
        raise HTTPException(404, "Client not found")

    quote = Quote(
        quote_number=_next_quote_number(db),
        client_id=body.client_id,
        created_by_id=current_user.id,
        title=body.title,
        description=body.description,
        site_address=body.site_address,
        notes=body.notes,
        gst_rate=body.gst_rate,
        valid_until=body.valid_until,
    )
    db.add(quote)
    db.flush()  # get quote.id before adding line items

    _apply_line_items(quote, body.line_items, db)
    _recalculate(quote)
    db.commit()
    quote = (
        db.query(Quote)
        .options(joinedload(Quote.line_items), joinedload(Quote.client))
        .filter(Quote.id == quote.id)
        .first()
    )
    return quote


@router.get("/{quote_id}", response_model=QuoteOut)
def get_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    quote = (
        db.query(Quote)
        .options(joinedload(Quote.line_items), joinedload(Quote.client))
        .filter(Quote.id == quote_id)
        .first()
    )
    if not quote:
        raise HTTPException(404, "Quote not found")
    return quote


@router.patch("/{quote_id}", response_model=QuoteOut)
def update_quote(
    quote_id: int,
    body: QuoteUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    quote = db.query(Quote).options(joinedload(Quote.line_items), joinedload(Quote.client)).filter(Quote.id == quote_id).first()
    if not quote:
        raise HTTPException(404, "Quote not found")

    updates = body.model_dump(exclude_unset=True, exclude={"line_items"})
    for field, value in updates.items():
        setattr(quote, field, value)

    if body.line_items is not None:
        _apply_line_items(quote, body.line_items, db)

    _recalculate(quote)
    db.commit()
    db.refresh(quote)
    return quote


@router.get("/{quote_id}/pdf")
def download_quote_pdf(
    quote_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    quote = (
        db.query(Quote)
        .options(joinedload(Quote.line_items), joinedload(Quote.client))
        .filter(Quote.id == quote_id)
        .first()
    )
    if not quote:
        raise HTTPException(404, "Quote not found")

    pdf_bytes = generate_quote_pdf(quote, settings.public_url)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Quote-{quote.quote_number}.pdf"'},
    )


@router.post("/{quote_id}/send", response_model=QuoteOut)
def send_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    quote = (
        db.query(Quote)
        .options(joinedload(Quote.line_items), joinedload(Quote.client))
        .filter(Quote.id == quote_id)
        .first()
    )
    if not quote:
        raise HTTPException(404, "Quote not found")
    if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.SENT):
        raise HTTPException(400, f"Cannot send a quote with status '{quote.status}'")

    approve_url = f"{settings.public_url}/quotes/public/{quote.quote_number}/approve"
    decline_url = f"{settings.public_url}/quotes/public/{quote.quote_number}/decline"

    pdf_bytes = generate_quote_pdf(quote, settings.public_url)

    if quote.client.email:
        send_quote_email(
            to_email=quote.client.email,
            to_name=quote.client.name,
            quote_number=quote.quote_number,
            quote_title=quote.title,
            pdf_bytes=pdf_bytes,
            approve_url=approve_url,
            decline_url=decline_url,
        )

    quote.status = QuoteStatus.SENT
    quote.sent_at = datetime.utcnow()
    db.commit()
    db.refresh(quote)
    return quote


@router.delete("/{quote_id}", status_code=204)
def delete_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    quote = db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(404, "Quote not found")
    if quote.status not in (QuoteStatus.DRAFT,):
        raise HTTPException(400, "Only draft quotes can be deleted")
    db.delete(quote)
    db.commit()


# Public endpoint — clients approve/decline without logging in
@router.post("/public/{quote_number}/approve")
def client_approve(quote_number: str, db: Session = Depends(get_db)):
    quote = db.query(Quote).filter(Quote.quote_number == quote_number).first()
    if not quote:
        raise HTTPException(404, "Quote not found")
    if quote.status != QuoteStatus.SENT:
        raise HTTPException(400, "Quote is not pending approval")
    quote.status = QuoteStatus.APPROVED
    quote.approved_at = datetime.utcnow()
    db.commit()
    return {"message": "Quote approved", "quote_number": quote_number}


@router.post("/public/{quote_number}/decline")
def client_decline(quote_number: str, db: Session = Depends(get_db)):
    quote = db.query(Quote).filter(Quote.quote_number == quote_number).first()
    if not quote:
        raise HTTPException(404, "Quote not found")
    if quote.status != QuoteStatus.SENT:
        raise HTTPException(400, "Quote is not pending approval")
    quote.status = QuoteStatus.DECLINED
    db.commit()
    return {"message": "Quote declined", "quote_number": quote_number}
