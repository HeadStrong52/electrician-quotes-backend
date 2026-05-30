import base64
import io
import re
from datetime import datetime
from fpdf import FPDF
from app.config import settings
from app.models.quote import Quote
from app.models.line_item import LineItemType

ORANGE     = (249, 115, 22)
ORANGE_DK  = (234, 88, 12)
ORANGE_BG  = (255, 247, 237)
DARK       = (26, 26, 26)
MID        = (100, 100, 100)
LIGHT      = (229, 231, 235)
PALE       = (249, 250, 251)
WHITE      = (255, 255, 255)

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


def _money(v) -> str:  return f"${float(v):,.2f}"
def _qty(v)   -> str:  return f"{float(v):g}"
def _date(v)  -> str:
    if isinstance(v, datetime):
        return f"{v.day} {v.strftime('%B %Y')}"
    return str(v) if v else ""


def _rgb(pdf, rgb, fill=False, draw=False, text=False):
    r, g, b = rgb
    if fill: pdf.set_fill_color(r, g, b)
    if draw: pdf.set_draw_color(r, g, b)
    if text: pdf.set_text_color(r, g, b)


def _logo_bytes(data_uri: str):
    try:
        m = re.match(r"data:image/(\w+);base64,(.+)", data_uri, re.DOTALL)
        if not m:
            return None
        t = m.group(1).upper()
        if t == "JPG": t = "JPEG"
        return base64.b64decode(m.group(2)), t
    except Exception:
        return None


def _deco_bar(pdf, x, y, w, flip=False):
    """Minimal orange accent: 0.8mm bar + 0.25mm underline."""
    bar_h = 0.8
    _rgb(pdf, ORANGE, fill=True, draw=True)
    if flip:
        pdf.set_line_width(0.25)
        pdf.line(x, y, x + w, y)
        pdf.rect(x, y + 1.0, w, bar_h, style="F")
    else:
        pdf.rect(x, y, w, bar_h, style="F")
        _rgb(pdf, ORANGE, draw=True)
        pdf.set_line_width(0.25)
        pdf.line(x, y + bar_h + 1.0, x + w, y + bar_h + 1.0)


class QuotePDF(FPDF):
    def __init__(self):
        super().__init__(unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=22)
        self.set_margins(15, 15, 15)
        self._footer_text = ""
        self.page_w = 210 - 30

    def set_footer_text(self, t: str):
        self._footer_text = t

    def normalize_text(self, text: str) -> str:
        return _safe(super().normalize_text(_safe(text)))

    def footer(self):
        _deco_bar(self, 15, self.h - 10, self.page_w, flip=True)
        self.set_y(self.h - 17)
        _rgb(self, MID, text=True)
        self.set_font("Helvetica", size=7.5)
        self.cell(0, 5, self._footer_text, align="C")
        self.set_x(15)
        self.cell(0, 5, f"Page {self.page_no()}", align="R")


def generate_quote_pdf(quote: Quote, base_url: str, user=None) -> bytes:
    pdf = QuotePDF()
    pdf.add_page()
    pw = pdf.page_w

    approve_url = f"{base_url}/quotes/public/{quote.quote_number}/approve"
    decline_url = f"{base_url}/quotes/public/{quote.quote_number}/decline"

    biz_name    = (user.business_name if user and user.business_name else None) or settings.business_name
    biz_phone   = (user.phone         if user and user.phone         else None) or settings.business_phone
    biz_email   = (user.email         if user                        else None) or settings.business_email
    biz_address = (user.address       if user and user.address       else None) or settings.business_address
    biz_rec     = (user.rec_licence   if user and user.rec_licence   else None)
    biz_logo    = (user.logo          if user and user.logo          else None)
    biz_abn     = settings.business_abn

    pdf.set_footer_text(
        f"All prices in Australian Dollars  |  Valid 30 days from issue  |  {biz_name}"
    )

    # ── TOP DECORATIVE BAR ──────────────────────────────────────
    bar_top = pdf.get_y()
    _deco_bar(pdf, pdf.l_margin, bar_top, pw)
    pdf.set_y(bar_top + 6)          # clear the bar + thin line + gap
    header_y = pdf.get_y()

    # ── LOGO ────────────────────────────────────────────────────
    logo_w = 0
    if biz_logo:
        decoded = _logo_bytes(biz_logo)
        if decoded:
            raw, img_type = decoded
            try:
                max_w, max_h = 30, 18
                pdf.image(io.BytesIO(raw), x=pdf.l_margin, y=header_y,
                          w=max_w, h=max_h, type=img_type, keep_aspect_ratio=True)
                logo_w = max_w + 4
            except Exception:
                logo_w = 0

    # ── LEFT COLUMN: business details ───────────────────────────
    lx  = pdf.l_margin + logo_w
    lcw = pw * 0.60 - logo_w

    pdf.set_xy(lx, header_y)
    _rgb(pdf, DARK, text=True)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(lcw, 9, _safe(biz_name), ln=True)

    _rgb(pdf, MID, text=True)
    pdf.set_font("Helvetica", size=8.5)
    sub = []
    if biz_rec:     sub.append(f"REC Licence: {biz_rec}")
    if biz_abn:     sub.append(f"ABN: {biz_abn}")
    if biz_address: sub.append(_safe(biz_address))
    contact = []
    if biz_phone:   contact.append(_safe(biz_phone))
    if biz_email:   contact.append(_safe(biz_email))
    if contact:     sub.append("  |  ".join(contact))
    for line in sub:
        pdf.set_x(lx)
        pdf.cell(lcw, 5, line, ln=True)

    left_end_y = pdf.get_y()

    # ── RIGHT COLUMN: quote number + status ─────────────────────
    rx  = pdf.l_margin + pw * 0.62
    rcw = pw * 0.38

    pdf.set_xy(rx, header_y)
    _rgb(pdf, MID, text=True)
    pdf.set_font("Helvetica", size=7.5)
    pdf.cell(rcw, 5, "QUOTE", align="R", ln=True)

    pdf.set_x(rx)
    _rgb(pdf, ORANGE, text=True)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(rcw, 10, quote.quote_number, align="R", ln=True)

    status_str = quote.status.value if hasattr(quote.status, "value") else str(quote.status)
    bg, fg = STATUS_COLORS.get(status_str, STATUS_COLORS["draft"])
    bw, bx = 32, pdf.l_margin + pw - 32
    by = pdf.get_y() + 1
    _rgb(pdf, bg, fill=True, draw=True)
    pdf.rect(bx, by, bw, 6, style="F")
    _rgb(pdf, fg, text=True)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_xy(bx, by + 0.5)
    pdf.cell(bw, 5, status_str.upper(), align="C")
    right_end_y = by + 7

    # Ensure we clear both columns before drawing the divider
    pdf.set_y(max(left_end_y, right_end_y) + 5)

    # ── DIVIDER ─────────────────────────────────────────────────
    _rgb(pdf, LIGHT, draw=True)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + pw, pdf.get_y())
    pdf.ln(6)

    # ── META GRID ───────────────────────────────────────────────
    col_w  = pw / 3
    meta_y = pdf.get_y()

    def meta_block(x, label, lines):
        pdf.set_xy(x, meta_y)
        _rgb(pdf, ORANGE, text=True)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(col_w, 4.5, label.upper(), ln=True)
        _rgb(pdf, DARK, text=True)
        pdf.set_font("Helvetica", size=9)
        for ln_ in lines:
            if ln_:
                pdf.set_x(x)
                pdf.multi_cell(col_w - 2, 5, _safe(str(ln_)))

    cl = [quote.client.name]
    if quote.client.address: cl.append(quote.client.address)
    if quote.client.phone:   cl.append(quote.client.phone)
    if quote.client.email:   cl.append(quote.client.email)
    meta_block(pdf.l_margin,          "Prepared for", cl)
    meta_block(pdf.l_margin + col_w,  "Site address",  [quote.site_address or "—"])
    dl = [_date(quote.created_at)]
    if quote.valid_until: dl.append(f"Valid until: {_date(quote.valid_until)}")
    meta_block(pdf.l_margin + col_w*2,"Date issued",   dl)

    pdf.set_y(meta_y + 30)
    _rgb(pdf, LIGHT, draw=True)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + pw, pdf.get_y())
    pdf.ln(6)

    # ── QUOTE TITLE ─────────────────────────────────────────────
    _rgb(pdf, DARK, text=True)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, _safe(quote.title), ln=True)
    if quote.description:
        _rgb(pdf, MID, text=True)
        pdf.set_font("Helvetica", size=9)
        pdf.multi_cell(0, 5, _safe(quote.description))
    pdf.ln(5)

    # ── LINE ITEMS ───────────────────────────────────────────────
    cd = pw * 0.50; cq = pw * 0.10; cu = pw * 0.10
    cp = pw * 0.14; ct = pw * 0.16

    def section_label(label):
        _rgb(pdf, ORANGE, text=True)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(0, 5.5, label.upper(), ln=True)
        pdf.ln(1)

    def table_hdr():
        _rgb(pdf, ORANGE, fill=True, draw=True)
        x, y = pdf.l_margin, pdf.get_y()
        pdf.rect(x, y, pw, 7, style="F")
        _rgb(pdf, WHITE, text=True)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_xy(x + 2, y + 0.8)
        pdf.cell(cd - 2, 5.5, "Description")
        pdf.cell(cq,  5.5, "Qty",        align="R")
        pdf.cell(cu,  5.5, "Unit",       align="C")
        pdf.cell(cp,  5.5, "Unit Price", align="R")
        pdf.cell(ct,  5.5, "Amount",     align="R", ln=True)
        pdf.ln(1)

    def table_rows(items):
        for i, item in enumerate(items):
            bg = PALE if i % 2 == 0 else WHITE
            _rgb(pdf, bg, fill=True, draw=True)
            y = pdf.get_y(); x = pdf.l_margin; rh = 6
            pdf.rect(x, y, pw, rh, style="F")
            _rgb(pdf, DARK, text=True)
            pdf.set_font("Helvetica", size=9)
            pdf.set_xy(x + 2, y + 0.8)
            pdf.cell(cd - 2, rh - 1, _safe(item.description))
            pdf.cell(cq, rh - 1, _qty(item.quantity), align="R")
            _rgb(pdf, MID, text=True)
            pdf.cell(cu, rh - 1, item.unit, align="C")
            _rgb(pdf, DARK, text=True)
            pdf.cell(cp, rh - 1, _money(item.unit_price), align="R")
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(ct, rh - 1, _money(item.total), align="R", ln=True)
            _rgb(pdf, LIGHT, draw=True)
            pdf.set_line_width(0.2)
            pdf.line(x, pdf.get_y(), x + pw, pdf.get_y())

    labour   = [i for i in quote.line_items if i.type == LineItemType.LABOUR]
    material = [i for i in quote.line_items if i.type == LineItemType.MATERIAL]
    other    = [i for i in quote.line_items if i.type == LineItemType.OTHER]

    for label, items in [("Labour", labour), ("Materials", material), ("Other", other)]:
        if not items: continue
        section_label(label)
        table_hdr()
        table_rows(items)
        pdf.ln(5)

    # ── TOTALS ───────────────────────────────────────────────────
    tw = 80; tx = pdf.l_margin + pw - tw
    pdf.ln(3)

    def totals_row(label, value, total=False):
        y = pdf.get_y()
        if total:
            _rgb(pdf, ORANGE, fill=True, draw=True)
            pdf.rect(tx, y, tw, 10, style="F")
            _rgb(pdf, WHITE, text=True)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_x(tx + 3); pdf.cell(tw * 0.55, 10, label)
            pdf.set_x(tx + tw * 0.55)
            pdf.cell(tw * 0.45 - 3, 10, value, align="R", ln=True)
        else:
            _rgb(pdf, PALE, fill=True, draw=True)
            pdf.rect(tx, y, tw, 7, style="F")
            _rgb(pdf, MID, text=True)
            pdf.set_font("Helvetica", size=9)
            pdf.set_x(tx + 3); pdf.cell(tw * 0.55, 7, label)
            _rgb(pdf, DARK, text=True)
            pdf.set_x(tx + tw * 0.55)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(tw * 0.45 - 3, 7, value, align="R", ln=True)
            _rgb(pdf, LIGHT, draw=True); pdf.set_line_width(0.2)
            pdf.line(tx, pdf.get_y(), tx + tw, pdf.get_y())

    gst_pct = int(float(quote.gst_rate) * 100)
    totals_row("Subtotal (ex GST)", _money(quote.subtotal))
    totals_row(f"GST ({gst_pct}%)", _money(quote.gst))
    pdf.ln(1)
    totals_row("TOTAL (inc. GST)", _money(quote.total), total=True)
    pdf.ln(8)

    # ── NOTES ────────────────────────────────────────────────────
    if quote.notes:
        section_label("Notes")
        nx, ny = pdf.l_margin, pdf.get_y()
        _rgb(pdf, ORANGE, fill=True)
        pdf.rect(nx, ny, 2.5, 18, style="F")
        _rgb(pdf, ORANGE_BG, fill=True, draw=True)
        pdf.rect(nx + 2.5, ny, pw - 2.5, 18, style="F")
        _rgb(pdf, DARK, text=True)
        pdf.set_font("Helvetica", size=9)
        pdf.set_xy(nx + 6, ny + 2)
        pdf.multi_cell(pw - 8, 5, _safe(quote.notes))
        pdf.ln(6)

    # ── CLIENT CTA (sent) ────────────────────────────────────────
    if status_str == "sent" and quote.client.email:
        cy = pdf.get_y()
        _rgb(pdf, ORANGE_BG, fill=True, draw=True)
        pdf.rect(pdf.l_margin, cy, pw, 24, style="F")
        _rgb(pdf, ORANGE, fill=True)
        pdf.rect(pdf.l_margin, cy, 2.5, 24, style="F")
        _rgb(pdf, DARK, text=True)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_xy(pdf.l_margin + 6, cy + 4)
        pdf.cell(0, 6, "Ready to proceed? Accept or decline this quote:", align="C", ln=True)
        _rgb(pdf, ORANGE, text=True)
        pdf.set_font("Helvetica", size=7.5)
        pdf.set_x(pdf.l_margin + 6)
        pdf.cell(0, 5, f"Accept:  {approve_url}", align="C", ln=True)
        _rgb(pdf, MID, text=True)
        pdf.set_x(pdf.l_margin + 6)
        pdf.cell(0, 5, f"Decline: {decline_url}", align="C", ln=True)

    return bytes(pdf.output())
