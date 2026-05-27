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
) -> None:
    """Send a quote PDF to a client via SMTP."""
    if not settings.smtp_host:
        raise RuntimeError("SMTP not configured — set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env")

    msg = EmailMessage()
    msg["Subject"] = f"Quote {quote_number} – {quote_title}"
    msg["From"] = f"{settings.business_name} <{settings.smtp_from or settings.smtp_user}>"
    msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
    msg["Reply-To"] = settings.business_email or settings.smtp_user

    # Plain text fallback
    msg.set_content(
        f"Hi {to_name or 'there'},\n\n"
        f"Please find attached your quote {quote_number} for {quote_title}.\n\n"
        f"To accept this quote, visit:\n{approve_url}\n\n"
        f"To decline, visit:\n{decline_url}\n\n"
        f"If you have any questions, please don't hesitate to get in touch.\n\n"
        f"Kind regards,\n{settings.business_name}"
    )

    # HTML body
    msg.add_alternative(
        f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#1a1a1a;max-width:560px;margin:0 auto;padding:24px">
  <p>Hi {to_name or 'there'},</p>
  <p>Please find attached your quote <strong>{quote_number}</strong> for <em>{quote_title}</em>.</p>
  <p style="margin:28px 0;text-align:center">
    <a href="{approve_url}"
       style="background:#16a34a;color:#fff;text-decoration:none;padding:12px 28px;border-radius:4px;font-weight:700;font-size:15px;margin-right:12px">
      Accept Quote
    </a>
    <a href="{decline_url}"
       style="color:#dc2626;text-decoration:none;padding:12px 16px;border:1.5px solid #dc2626;border-radius:4px;font-weight:600;font-size:14px">
      Decline
    </a>
  </p>
  <p>If you have any questions, please don't hesitate to get in touch.</p>
  <p>Kind regards,<br><strong>{settings.business_name}</strong></p>
  {"<p style='color:#888;font-size:11px'>"+settings.business_phone+"</p>" if settings.business_phone else ""}
</body>
</html>""",
        subtype="html",
    )

    # Attach PDF
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"Quote-{quote_number}.pdf",
    )

    port = settings.smtp_port
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, port) as smtp:
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
