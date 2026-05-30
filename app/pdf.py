import base64
import io
import re
from datetime import datetime
from fpdf import FPDF
from app.config import settings
from app.models.quote import Quote
from app.models.line_item import LineItemType

# Colour palette
ORANGE = (249, 115, 22)   # brand orange #f97316
ORANGE_DARK = (234, 88, 12)
DARK   = (26, 26, 26)
MID    = (100, 100, 100)
LIGHT  = (229, 231, 235)
PALE   = (249, 250, 251)
WHITE  = (255, 255, 255)
ORANGE_BG = (255, 247, 237)   # very light orange tint

STATUS_COLORS = {
    "draft":    ((229, 231, 235), (55, 65, 81)),
    "sent":     ((219, 234, 254), (29, 78, 216)),
    "approved": ((220, 252, 231), (21, 128, 61)),
    "declined": ((254, 226, 226), (185, 28, 28)),
    "invoiced": ((254, 243, 199), (146, 64, 14)),
    "paid":     ((209, 250, 229), (6, 95, 70)),
}

_UNICODE_MAP = {
    "—": " - ", "–": "-",
    "‘": "'",   "’": "'",
    "“": '"',   "”": '"',
    "…": "...", " ": " ",
}


def _safe(text: str) -> str:
    for k, v in _UNICODE_MAP.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _money(v) -> str:
    return f"${float(v):,.2f}"

def _qty(v) -> str:
    return f"{float(v):g}"

def _date(v) -> str:
    if isinstance(v, datetime):
        return f"{v.day} {v.strftime('%B %Y')}"
    return str(v) if v else ""

def _set_color(pdf, rgb, fill=False, draw=False, text=False):
    r, g, b = rgb
    if fill: pdf.set_fill_color(r, g, b)
    if draw: pdf.set_draw_color(r, g, b)
    if text: pdf.set_text_color(r, g, b)


def _logo_bytes(data_uri: str):
    try:
        m = re.match(r"data:image/(\w+);base64,(.+)", data_uri, re.DOTALL)
        if not m:
            return None
        img_type = m.group(1).upper()
        if img_type == "JPG":
            img_type = "JPEG"
        return base64.b64decode(m.group(2)), img_type
    except Exception:
        return None


def _draw_deco_bar(pdf: FPDF, x: float, y: float, w: float, flip: bool = False):
    """Decorative electrical-style double bar — thick + thin with connector notches."""
    if flip:
        # Bottom version: thin line then thick bar
        _set_color(pdf, ORANGE, fill=True, draw=True)
        pdf.set_line_width(0.4)
        pdf.line(x, y, x + w, y)
        pdf.rect(x, y + 2.5, w, 3.5, style="F")
        # connector notches (white cuts)
        _set_color(pdf, WHITE, fill=True, draw=True)
        spacing = 18.0
        nx = x + spacing
        while nx < x + w - 8:
            pdf.rect(nx, y + 2.5, 1.2, 3.5, style="F")
            nx += spacing
        # small end caps
        _set_color(pdf, ORANGE_DARK, fill=True, draw=True)
        pdf.rect(x, y + 2.5, 3.5, 3.5, style="F")
        pdf.rect(x + w - 3.5, y + 2.5, 3.5, 3.5, style="F")
    else:
        # Top version: thick bar then thin line
        _set_color(pdf, ORANGE, fill=True, draw=True)
        pdf.rect(x, y, w, 3.5, style="F")
        # connector notches (white cuts through bar)
        _set_color(pdf, WHITE, fill=True, draw=True)
        spacing = 18.0
        nx = x + spacing
        while nx < x + w - 8:
            pdf.rect(nx, y, 1.2, 3.5, style="F")
            nx += spacing
        # small end caps (darker orange)
        _set_color(pdf, ORANGE_DARK, fill=True, draw=True)
        pdf.rect(x, y, 3.5, 3.5, style="F")
        pdf.rect(x + w - 3.5, y, 3.5, 3.5, style="F")
        # thin line below
        _set_color(pdf, ORANGE, fill=True, draw=True)
        pdf.set_line_width(0.5)
        pdf.line(x, y + 5.5, x + w, y + 5.5)


class QuotePDF(FPDF):
    def __init__(self):
        super().__init__(unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=22)
        self.set_margins(15, 15, 15)
        self._footer_text = ""
        self._page_w = 210 - 30  # A4 minus margins

    def set_footer_text(self, text: str):
        self._footer_text = text

    def normalize_text(self, text: str) -> str:
        return _safe(super().normalize_text(_safe(text)))

    def footer(self):
        # Decorative bottom bar
        _draw_deco_bar(self, 15, self.h - 12, self._page_w, flip=True)
        # Footer text
        self.set_y(self.h - 18)
        _set_color(self, MID, text=True)
        self.set_font("Helvetica", size=7.5)
        self.set_x(15)
        self.cell(0, 5, self._footer_text, align="C")
        self.set_x(15)
        self.cell(0, 5, f"Page {self.page_no()}", align="R")


def generate_quote_pdf(quote: Quote, base_url: str, user=None) -> bytes:
    pdf = QuotePDF()
    pdf.add_page()

    approve_url = f"{base_url}/quotes/public/{quote.quote_number}/approve"
    decline_url = f"{base_url}/quotes/public/{quote.quote_number}/decline"

    biz_name    = (user.business_name if user and user.business_name else None) or settings.business_name
    biz_phone   = (user.phone         if user and user.phone         else None) or settings.business_phone
    biz_email   = (user.email         if user                        else None) or settings.business_email
    biz_address = (user.address       if user and user.address       else None) or settings.business_address
    biz_rec     = (user.rec_licence   if user and user.rec_licence   else None)
    biz_logo    = (user.logo          if user and user.logo          else None)
    biz_abn     = settings.business_abn

    page_w = pdf._page_w

    pdf.set_footer_text(
        f"All prices in Australian Dollars  |  Valid 30 days from issue  |  {biz_name}"
    )

    # ── TOP DECORATIVE BAR ─────────────────────────────────────
    _draw_deco_bar(pdf, pdf.l_margin, pdf.get_y(), page_w)
    pdf.ln(10)
    header_y = pdf.get_y()

    # ── LOGO ───────────────────────────────────────────────────
    logo_w = 0
    if biz_logo:
        decoded = _logo_bytes(biz_logo)
        if decoded:
            raw, img_type = decoded
            try:
                max_w, max_h = 32, 20
                pdf.image(io.BytesIO(raw), x=pdf.l_margin, y=header_y,
                          w=max_w, h=max_h, type=img_type, keep_aspect_ratio=True)
                logo_w = max_w + 4
            except Exception:
                logo_w = 0

    # ── BUSINESS NAME & DETAILS (left column) ─────────────────
    text_x = pdf.l_margin + logo_w
    text_w = page_w * 0.60 - logo_w

    pdf.set_xy(text_x, header_y)
    _set_color(pdf, DARK, text=True)
    pdf.set_font("Helvetica", "B", 17)
    pdf.cell(text_w, 9, _safe(biz_name), ln=True)

    # Sub-details
    _set_color(pdf, MID, text=True)
    pdf.set_font("Helvetica", size=8.5)
    sub_lines = []
    if biz_rec:
        sub_lines.append(f"REC Licence: {biz_rec}")
    if biz_abn:
        sub_lines.append(f"ABN: {biz_abn}")
    if biz_address:
        sub_lines.append(_safe(biz_address))
    contact = []
    if biz_phone:
        contact.append(_safe(biz_phone))
    if biz_email:
        contact.append(_safe(biz_email))
    if contact:
        sub_lines.append("  |  ".join(contact))
    for line in sub_lines:
        pdf.set_x(text_x)
        pdf.cell(text_w, 5, line, ln=True)

    # ── QUOTE NUMBER & STATUS (right column) ──────────────────
    right_x = pdf.l_margin + page_w * 0.62
    right_w = page_w * 0.38

    pdf.set_xy(right_x, header_y)
    _set_color(pdf, MID, text=True)
    pdf.set_font("Helvetica", size=7.5)
    pdf.cell(right_w, 5, "QUOTE", align="R", ln=True)

    pdf.set_x(right_x)
    _set_color(pdf, ORANGE, text=True)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(right_w, 10, quote.quote_number, align="R", ln=True)

    # Status badge
    status_str = quote.status.value if hasattr(quote.status, "value") else str(quote.status)
    bg, fg = STATUS_COLORS.get(status_str, STATUS_COLORS["draft"])
    badge_w = 32
    badge_x = pdf.l_margin + page_w - badge_w
    badge_y = pdf.get_y() + 1
    _set_color(pdf, bg, fill=True, draw=True)
    pdf.rect(badge_x, badge_y, badge_w, 6, style="F")
    _set_color(pdf, fg, text=True)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_xy(badge_x, badge_y + 0.5)
    pdf.cell(badge_w, 5, status_str.upper(), align="C")

    # Advance Y past logo/header block
    logo_bottom = header_y + 22
    pdf.set_y(max(pdf.get_y() + 4, logo_bottom))

    # ── DIVIDER ────────────────────────────────────────────────
    _set_color(pdf, LIGHT, draw=True)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_w, pdf.get_y())
    pdf.ln(6)

    # ── META GRID ──────────────────────────────────────────────
    col_w = page_w / 3
    meta_y = pdf.get_y()

    def meta_block(x, y, label, lines):
        pdf.set_xy(x, y)
        _set_color(pdf, ORANGE, text=True)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(col_w, 4.5, label.upper(), ln=True)
        _set_color(pdf, DARK, text=True)
        pdf.set_font("Helvetica", size=9)
        for line in lines:
            if line:
                pdf.set_x(x)
                pdf.multi_cell(col_w - 2, 5, _safe(str(line)))

    client_lines = [quote.client.name]
    if quote.client.address:
        client_lines.append(quote.client.address)
    if quote.client.phone:
        client_lines.append(quote.client.phone)
    if quote.client.email:
        client_lines.append(quote.client.email)
    meta_block(pdf.l_margin, meta_y, "Prepared for", client_lines)
    meta_block(pdf.l_margin + col_w, meta_y, "Site address", [quote.site_address or "—"])
    date_lines = [_date(quote.created_at)]
    if quote.valid_until:
        date_lines.append(f"Valid until: {_date(quote.valid_until)}")
    meta_block(pdf.l_margin + col_w * 2, meta_y, "Date issued", date_lines)

    pdf.set_y(meta_y + 30)
    _set_color(pdf, LIGHT, draw=True)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_w, pdf.get_y())
    pdf.ln(6)

    # ── QUOTE TITLE ────────────────────────────────────────────
    _set_color(pdf, DARK, text=True)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, _safe(quote.title), ln=True)
    if quote.description:
        _set_color(pdf, MID, text=True)
        pdf.set_font("Helvetica", size=9)
        pdf.multi_cell(0, 5, _safe(quote.description))
    pdf.ln(5)

    # ── LINE ITEMS TABLE ───────────────────────────────────────
    col_desc  = page_w * 0.50
    col_qty   = page_w * 0.10
    col_unit  = page_w * 0.10
    col_price = page_w * 0.14
    col_total = page_w * 0.16

    def section_heading(label):
        _set_color(pdf, ORANGE, text=True)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(0, 5.5, label.upper(), ln=True)
        pdf.ln(1)

    def table_header():
        # Orange header bar
        _set_color(pdf, ORANGE, fill=True, draw=True)
        x, y = pdf.l_margin, pdf.get_y()
        pdf.rect(x, y, page_w, 7, style="F")
        _set_color(pdf, WHITE, text=True)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_xy(x + 2, y + 0.7)
        pdf.cell(col_desc - 2, 5.5, "Description")
        pdf.cell(col_qty,  5.5, "Qty",        align="R")
        pdf.cell(col_unit, 5.5, "Unit",       align="C")
        pdf.cell(col_price,5.5, "Unit Price", align="R")
        pdf.cell(col_total,5.5, "Amount",     align="R", ln=True)
        pdf.ln(1)

    def table_rows(items):
        for idx, item in enumerate(items):
            bg = PALE if idx % 2 == 0 else WHITE
            _set_color(pdf, bg, fill=True, draw=True)
            y = pdf.get_y()
            row_h = 6
            x = pdf.l_margin
            pdf.rect(x, y, page_w, row_h, style="F")
            _set_color(pdf, DARK, text=True)
            pdf.set_font("Helvetica", size=9)
            pdf.set_xy(x + 2, y + 0.7)
            pdf.cell(col_desc - 2, row_h - 1, _safe(item.description))
            pdf.cell(col_qty,   row_h - 1, _qty(item.quantity),     align="R")
            _set_color(pdf, MID, text=True)
            pdf.cell(col_unit,  row_h - 1, item.unit,               align="C")
            _set_color(pdf, DARK, text=True)
            pdf.cell(col_price, row_h - 1, _money(item.unit_price), align="R")
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(col_total, row_h - 1, _money(item.total),      align="R", ln=True)
            _set_color(pdf, LIGHT, draw=True)
            pdf.set_line_width(0.2)
            pdf.line(x, pdf.get_y(), x + page_w, pdf.get_y())

    labour_items   = [i for i in quote.line_items if i.type == LineItemType.LABOUR]
    material_items = [i for i in quote.line_items if i.type == LineItemType.MATERIAL]
    other_items    = [i for i in quote.line_items if i.type == LineItemType.OTHER]

    for label, items in [("Labour", labour_items), ("Materials", material_items), ("Other", other_items)]:
        if not items:
            continue
        section_heading(label)
        table_header()
        table_rows(items)
        pdf.ln(5)

    # ── TOTALS ─────────────────────────────────────────────────
    totals_w = 80
    totals_x = pdf.l_margin + page_w - totals_w
    pdf.ln(3)

    def totals_row(label, value, is_total=False):
        if is_total:
            # Orange fill for TOTAL row
            _set_color(pdf, ORANGE, fill=True, draw=True)
            pdf.rect(totals_x, pdf.get_y(), totals_w, 10, style="F")
            _set_color(pdf, WHITE, text=True)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_x(totals_x + 3)
            pdf.cell(totals_w * 0.55, 10, label)
            pdf.set_x(totals_x + totals_w * 0.55)
            pdf.cell(totals_w * 0.45 - 3, 10, value, align="R", ln=True)
        else:
            _set_color(pdf, PALE, fill=True, draw=True)
            pdf.rect(totals_x, pdf.get_y(), totals_w, 7, style="F")
            _set_color(pdf, MID, text=True)
            pdf.set_font("Helvetica", size=9)
            pdf.set_x(totals_x + 3)
            pdf.cell(totals_w * 0.55, 7, label)
            _set_color(pdf, DARK, text=True)
            pdf.set_x(totals_x + totals_w * 0.55)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(totals_w * 0.45 - 3, 7, value, align="R", ln=True)
            _set_color(pdf, LIGHT, draw=True)
            pdf.set_line_width(0.2)
            pdf.line(totals_x, pdf.get_y(), totals_x + totals_w, pdf.get_y())

    gst_pct = int(float(quote.gst_rate) * 100)
    totals_row("Subtotal (ex GST)", _money(quote.subtotal))
    totals_row(f"GST ({gst_pct}%)", _money(quote.gst))
    pdf.ln(1)
    totals_row("TOTAL (inc. GST)", _money(quote.total), is_total=True)
    pdf.ln(8)

    # ── NOTES ──────────────────────────────────────────────────
    if quote.notes:
        _set_color(pdf, ORANGE, text=True)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(0, 5.5, "NOTES", ln=True)
        pdf.ln(1)
        note_x = pdf.l_margin
        note_y = pdf.get_y()
        # Orange left accent bar
        _set_color(pdf, ORANGE, fill=True, draw=True)
        pdf.rect(note_x, note_y, 2.5, 18, style="F")
        _set_color(pdf, ORANGE_BG, fill=True, draw=True)
        pdf.rect(note_x + 2.5, note_y, page_w - 2.5, 18, style="F")
        _set_color(pdf, DARK, text=True)
        pdf.set_font("Helvetica", size=9)
        pdf.set_xy(note_x + 6, note_y + 2)
        pdf.multi_cell(page_w - 8, 5, _safe(quote.notes))
        pdf.ln(6)

    # ── CLIENT CTA (sent quotes only) ─────────────────────────
    if status_str == "sent" and quote.client.email:
        _set_color(pdf, ORANGE_BG, fill=True, draw=True)
        cta_y = pdf.get_y()
        pdf.rect(pdf.l_margin, cta_y, page_w, 24, style="F")
        # Orange left accent
        _set_color(pdf, ORANGE, fill=True)
        pdf.rect(pdf.l_margin, cta_y, 2.5, 24, style="F")
        _set_color(pdf, DARK, text=True)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_xy(pdf.l_margin + 6, cta_y + 4)
        pdf.cell(0, 6, "Ready to proceed? Accept or decline this quote:", align="C", ln=True)
        _set_color(pdf, ORANGE, text=True)
        pdf.set_font("Helvetica", size=7.5)
        pdf.set_x(pdf.l_margin + 6)
        pdf.cell(0, 5, f"Accept:  {approve_url}", align="C", ln=True)
        _set_color(pdf, MID, text=True)
        pdf.set_x(pdf.l_margin + 6)
        pdf.cell(0, 5, f"Decline: {decline_url}", align="C", ln=True)

    return bytes(pdf.output())
