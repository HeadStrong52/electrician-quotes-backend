import smtplib
from email.message import EmailMessage
from app.config import settings


def send_quote_email(
    *,
    to_email: str,
    to_name: str,
    quote_number: str,
    quote_title: str,
    pdf_bytes: bytes,
    approve_url: str,
    decline_url: str,
    sender_name: str = "",
    sender_phone: str = "",
    sender_email: str = "",
) -> None:
    """Send a quote PDF to a client via SMTP."""
    if not settings.smtp_host:
        raise RuntimeError("SMTP not configured — set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in Railway variables")

    biz_name  = sender_name  or settings.business_name
    biz_phone = sender_phone or settings.business_phone
    biz_email = sender_email or settings.business_email or settings.smtp_user
    from_addr = settings.smtp_from or settings.smtp_user

    msg = EmailMessage()
    msg["Subject"] = f"Quote {quote_number} – {quote_title}"
    msg["From"]    = f"{biz_name} <{from_addr}>"
    msg["To"]      = f"{to_name} <{to_email}>" if to_name else to_email
    msg["Reply-To"] = biz_email

    msg.set_content(
        f"Hi {to_name or 'there'},\n\n"
        f"Please find attached your quote {quote_number} for {quote_title}.\n\n"
        f"To accept this quote, visit:\n{approve_url}\n\n"
        f"To decline, visit:\n{decline_url}\n\n"
        f"If you have any questions, please don't hesitate to get in touch.\n\n"
        f"Kind regards,\n{biz_name}"
        + (f"\n{biz_phone}" if biz_phone else "")
    )

    phone_line = f"<p style='color:#888;font-size:12px;margin-top:4px'>{biz_phone}</p>" if biz_phone else ""
    msg.add_alternative(
        f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#1a1a1a;max-width:560px;margin:0 auto;padding:24px">
  <div style="border-top:4px solid #f97316;margin-bottom:28px"></div>
  <p>Hi {to_name or 'there'},</p>
  <p>Please find attached your quote <strong>{quote_number}</strong> for <em>{quote_title}</em>.</p>
  <p>The PDF is attached to this email. You can also accept or decline the quote using the buttons below.</p>
  <p style="margin:32px 0;text-align:center">
    <a href="{approve_url}"
       style="background:#f97316;color:#fff;text-decoration:none;padding:13px 32px;border-radius:6px;font-weight:700;font-size:15px;margin-right:12px;display:inline-block">
      ✓ Accept Quote
    </a>
    <a href="{decline_url}"
       style="color:#dc2626;text-decoration:none;padding:12px 20px;border:1.5px solid #dc2626;border-radius:6px;font-weight:600;font-size:14px;display:inline-block">
      Decline
    </a>
  </p>
  <p>If you have any questions, please don't hesitate to get in touch.</p>
  <p>Kind regards,<br><strong>{biz_name}</strong></p>
  {phone_line}
  <div style="border-top:1px solid #e5e7eb;margin-top:32px;padding-top:12px;color:#9ca3af;font-size:11px">
    This quote was sent via Elec Connect
  </div>
</body>
</html>""",
        subtype="html",
    )

    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"Quote-{quote_number}.pdf",
    )

    port = settings.smtp_port
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, port, timeout=8) as smtp:
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, port, timeout=8) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
