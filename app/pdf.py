from datetime import datetime
from fpdf import FPDF
from app.config import settings
from app.models.quote import Quote
from app.models.line_item import LineItemType

# Colour palette
AMBER = (245, 158, 11)
DARK  = (26, 26, 26)
MID   = (85, 85, 85)
LIGHT = (229, 231, 235)
PALE  = (249, 250, 251)
WHITE = (255, 255, 255)

STATUS_COLORS = {
    "draft":    ((229, 231, 235), (55, 65, 81)),
    "sent":     ((219, 234, 254), (29, 78, 216)),
    "approved": ((220, 252, 231), (21, 128, 61)),
    "declined": ((254, 226, 226), (185, 28, 28)),
    "invoiced": ((254, 243, 199), (146, 64, 14)),
    "paid":     ((209, 250, 229), (6, 95, 70)),
}


_UNICODE_MAP = {
    "—": " - ",  # em dash
    "–": "-",    # en dash
    "‘": "'",    # left single quote
    "’": "'",    # right single quote
    "“": '"',    # left double quote
    "”": '"',    # right double quote
    "…": "...",  # ellipsis
    " ": " ",    # non-breaking space
}


def _safe(text: str) -> str:
    for k, v in _UNICODE_MAP.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _money(v) -> str:
    return f"${float(v):,.2f}"


def _qty(v) -> str:
    f = float(v)
    return f"{f:g}"


def _date(v) -> str:
    if isinstance(v, datetime):
        return f"{v.day} {v.strftime('%B %Y')}"
    return str(v) if v else ""


def _set_color(pdf: FPDF, rgb: tuple, fill=False, draw=False, text=False):
    r, g, b = rgb
    if fill:
        pdf.set_fill_color(r, g, b)
    if draw:
        pdf.set_draw_color(r, g, b)
    if text:
        pdf.set_text_color(r, g, b)


class QuotePDF(FPDF):
    def __init__(self):
        super().__init__(unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(15, 15, 15)
        self._footer_text = ""

    def set_footer_text(self, text: str):
        self._footer_text = text

    def normalize_text(self, text: str) -> str:
        return _safe(super().normalize_text(_safe(text)))

    def footer(self):
        self.set_y(-15)
        _set_color(self, MID, text=True)
        self.set_font("Helvetica", size=8)
        self.cell(0, 5, self._footer_text, align="C")
        self.set_x(15)
        self.cell(0, 5, f"Page {self.page_no()}", align="R")


def generate_quote_pdf(quote: Quote, base_url: str) -> bytes:
    pdf = QuotePDF()
    pdf.add_page()

    approve_url = f"{base_url}/quotes/public/{quote.quote_number}/approve"
    decline_url = f"{base_url}/quotes/public/{quote.quote_number}/decline"

    biz = settings
    pdf.set_footer_text(
        "All prices in Australian Dollars. "
        f"Valid 30 days from issue. | {biz.business_name}"
    )

    # ── HEADER ───────────────────────────────────────────────────
    page_w = pdf.w - pdf.l_margin - pdf.r_margin  # usable width

    # Amber top bar
    _set_color(pdf, AMBER, fill=True, draw=True)
    pdf.rect(pdf.l_margin, pdf.get_y(), page_w, 1.2, style="F")
    pdf.ln(4)

    header_y = pdf.get_y()

    # Left — business name
    pdf.set_x(pdf.l_margin)
    _set_color(pdf, DARK, text=True)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(page_w * 0.60, 9, biz.business_name, ln=False)

    # Right — "QUOTE" label + number
    right_x = pdf.l_margin + page_w * 0.60
    pdf.set_xy(right_x, header_y)
    _set_color(pdf, MID, text=True)
    pdf.set_font("Helvetica", size=7)
    pdf.cell(page_w * 0.40, 4, "QUOTE", align="R", ln=True)

    pdf.set_x(right_x)
    _set_color(pdf, AMBER, text=True)
    pdf.set_font("Helvetica", "B", 17)
    pdf.cell(page_w * 0.40, 8, quote.quote_number, align="R", ln=True)

    # Status badge
    status_str = quote.status.value if hasattr(quote.status, "value") else str(quote.status)
    bg, fg = STATUS_COLORS.get(status_str, STATUS_COLORS["draft"])
    badge_w = 28
    badge_x = pdf.l_margin + page_w - badge_w
    badge_y = pdf.get_y() + 1
    _set_color(pdf, bg, fill=True, draw=True)
    pdf.rect(badge_x, badge_y, badge_w, 5.5, style="F")
    _set_color(pdf, fg, text=True)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_xy(badge_x, badge_y + 0.5)
    pdf.cell(badge_w, 4.5, status_str.upper(), align="C")

    pdf.set_y(header_y + 9)

    # Business sub-details
    _set_color(pdf, MID, text=True)
    pdf.set_font("Helvetica", size=8)
    details = []
    if biz.business_abn:
        details.append(f"ABN {biz.business_abn}")
    if biz.business_address:
        details.append(biz.business_address)
    contact = []
    if biz.business_phone:
        contact.append(biz.business_phone)
    if biz.business_email:
        contact.append(biz.business_email)
    if contact:
        details.append("  |  ".join(contact))
    for line in details:
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 4.5, line, ln=True)

    pdf.ln(4)
    # Divider
    _set_color(pdf, LIGHT, draw=True)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_w, pdf.get_y())
    pdf.ln(5)

    # ── META GRID ────────────────────────────────────────────────
    col_w = page_w / 3
    meta_y = pdf.get_y()

    def meta_block(x, y, label, lines):
        pdf.set_xy(x, y)
        _set_color(pdf, MID, text=True)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(col_w, 4, label.upper())
        pdf.set_xy(x, y + 4.5)
        _set_color(pdf, DARK, text=True)
        pdf.set_font("Helvetica", size=9)
        for line in lines:
            if line:
                pdf.set_x(x)
                pdf.multi_cell(col_w - 2, 4.5, line)

    # Client
    client_lines = [quote.client.name]
    if quote.client.address:
        client_lines.append(quote.client.address)
    if quote.client.phone:
        client_lines.append(quote.client.phone)
    if quote.client.email:
        client_lines.append(quote.client.email)
    meta_block(pdf.l_margin, meta_y, "Prepared for", client_lines)

    # Site
    site_lines = [quote.site_address or "-"]
    meta_block(pdf.l_margin + col_w, meta_y, "Site address", site_lines)

    # Dates
    date_lines = [_date(quote.created_at)]
    if quote.valid_until:
        date_lines.append(f"Valid until: {_date(quote.valid_until)}")
    meta_block(pdf.l_margin + col_w * 2, meta_y, "Date issued", date_lines)

    pdf.set_y(meta_y + 28)
    _set_color(pdf, LIGHT, draw=True)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_w, pdf.get_y())
    pdf.ln(5)

    # ── TITLE ────────────────────────────────────────────────────
    _set_color(pdf, DARK, text=True)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 7, quote.title, ln=True)
    if quote.description:
        _set_color(pdf, MID, text=True)
        pdf.set_font("Helvetica", size=9)
        pdf.multi_cell(0, 5, quote.description)
    pdf.ln(4)

    # ── LINE ITEMS TABLE ─────────────────────────────────────────
    def section_heading(label):
        _set_color(pdf, AMBER, text=True)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(0, 5, label.upper(), ln=True)
        pdf.ln(1)

    col_desc  = page_w * 0.50
    col_qty   = page_w * 0.10
    col_unit  = page_w * 0.10
    col_price = page_w * 0.14
    col_total = page_w * 0.16

    def table_header():
        _set_color(pdf, DARK, fill=True, draw=True)
        pdf.set_fill_color(*DARK)
        _set_color(pdf, WHITE, text=True)
        pdf.set_font("Helvetica", "B", 8)
        x = pdf.l_margin
        y = pdf.get_y()
        pdf.rect(x, y, page_w, 6.5, style="F")
        pdf.set_xy(x + 2, y + 0.5)
        pdf.cell(col_desc - 2, 5.5, "Description")
        pdf.cell(col_qty,  5.5, "Qty",        align="R")
        pdf.cell(col_unit, 5.5, "Unit",       align="C")
        pdf.cell(col_price,5.5, "Unit price", align="R")
        pdf.cell(col_total,5.5, "Amount",     align="R", ln=True)
        pdf.ln(1)

    def table_rows(items):
        for idx, item in enumerate(items):
            bg = PALE if idx % 2 == 0 else WHITE
            _set_color(pdf, bg, fill=True, draw=True)
            y = pdf.get_y()
            # Measure description height
            pdf.set_font("Helvetica", size=9)
            row_h = 5.5
            x = pdf.l_margin
            pdf.rect(x, y, page_w, row_h, style="F")
            _set_color(pdf, DARK, text=True)
            pdf.set_xy(x + 2, y + 0.5)
            pdf.cell(col_desc - 2, row_h - 1, item.description, ln=False)
            _set_color(pdf, DARK, text=True)
            pdf.cell(col_qty,   row_h - 1, _qty(item.quantity),        align="R")
            _set_color(pdf, MID, text=True)
            pdf.cell(col_unit,  row_h - 1, item.unit,                  align="C")
            _set_color(pdf, DARK, text=True)
            pdf.cell(col_price, row_h - 1, _money(item.unit_price),    align="R")
            pdf.cell(col_total, row_h - 1, _money(item.total),         align="R", ln=True)
            # Bottom border
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
        pdf.ln(4)

    # ── TOTALS ───────────────────────────────────────────────────
    totals_w = 75
    totals_x = pdf.l_margin + page_w - totals_w
    pdf.ln(2)

    def totals_row(label, value, bold=False, big=False):
        if big:
            _set_color(pdf, DARK, fill=True)
            pdf.rect(totals_x, pdf.get_y(), totals_w, 9, style="F")
            _set_color(pdf, WHITE, text=True)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_x(totals_x + 2)
            pdf.cell(totals_w * 0.55, 9, label)
            pdf.set_x(totals_x + totals_w * 0.55)
            pdf.cell(totals_w * 0.45 - 2, 9, value, align="R", ln=True)
        else:
            _set_color(pdf, MID, text=True)
            pdf.set_font("Helvetica", size=9)
            pdf.set_x(totals_x + 2)
            pdf.cell(totals_w * 0.55, 6, label)
            _set_color(pdf, DARK, text=True)
            pdf.set_x(totals_x + totals_w * 0.55)
            pdf.cell(totals_w * 0.45 - 2, 6, value, align="R", ln=True)
            _set_color(pdf, LIGHT, draw=True)
            pdf.set_line_width(0.2)
            pdf.line(totals_x, pdf.get_y(), totals_x + totals_w, pdf.get_y())

    gst_pct = int(float(quote.gst_rate) * 100)
    totals_row("Subtotal (ex GST)", _money(quote.subtotal))
    totals_row(f"GST ({gst_pct}%)", _money(quote.gst))
    pdf.ln(1)
    totals_row("TOTAL", _money(quote.total), big=True)
    pdf.ln(8)

    # ── NOTES ────────────────────────────────────────────────────
    if quote.notes:
        section_heading("Notes")
        _set_color(pdf, PALE, fill=True, draw=True)
        note_x = pdf.l_margin
        note_y = pdf.get_y()
        _set_color(pdf, AMBER, draw=True)
        pdf.set_line_width(1.0)
        pdf.line(note_x, note_y, note_x, note_y + 20)
        pdf.set_line_width(0.2)
        _set_color(pdf, PALE, fill=True, draw=True)
        pdf.rect(note_x + 1.5, note_y, page_w - 1.5, 20, style="F")
        _set_color(pdf, MID, text=True)
        pdf.set_font("Helvetica", size=9)
        pdf.set_xy(note_x + 4, note_y + 2)
        pdf.multi_cell(page_w - 6, 5, quote.notes)
        pdf.ln(6)

    # ── CLIENT CTA (sent quotes only) ────────────────────────────
    if status_str == "sent" and quote.client.email:
        _set_color(pdf, PALE, fill=True, draw=True)
        cta_y = pdf.get_y()
        pdf.rect(pdf.l_margin, cta_y, page_w, 22, style="F")
        _set_color(pdf, DARK, text=True)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_xy(pdf.l_margin, cta_y + 3)
        pdf.cell(0, 6, "Ready to proceed? Accept or decline this quote:", align="C", ln=True)
        pdf.set_font("Helvetica", size=8)
        _set_color(pdf, MID, text=True)
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 5, f"Accept: {approve_url}", align="C", ln=True)
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 5, f"Decline: {decline_url}", align="C", ln=True)

    return bytes(pdf.output())
