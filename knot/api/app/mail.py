"""Sign-in code emails via Resend.

What shows on her lock screen is the sender, the subject and the first line of text, so those
three stay neutral ("no-reply", "Your code: 482913", "Your sign-in code is …"). The inside of the
email matches the app: plum night palette, serif headings, the code in a box like the app's
code boxes.

Email apps don't understand modern CSS, so everything is inline, laid out with tables, and
colours are plain hex (the app's oklch tokens converted: see web/src/lib/theme.ts).
"""

import logging
from html import escape

import httpx

from .config import get_settings

log = logging.getLogger("knot.mail")

# Plum night palette, as hex.
BG2 = "#13050f"
BG = "#230d1c"
SURFACE = "#321b2b"
LINE = "#5b4152"
INK = "#f3eee6"
MUTED = "#c2adba"
ACCENT = "#f8a187"

SERIF = "'Cormorant Garamond', Georgia, 'Times New Roman', serif"
SANS = "Manrope, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
MONO = "ui-monospace, Menlo, Consolas, 'Courier New', monospace"


def render_text(code: str, minutes: int) -> str:
    # Plain-text version. Also what iOS reads to offer the code above the keyboard.
    return (
        f"Your sign-in code is {code}\n\n"
        f"It works for {minutes} minutes.\n"
        "If you didn't ask for it, you can safely ignore this email."
    )


def render_html(code: str, minutes: int) -> str:
    code = escape(code)
    # Hidden "preheader": the line email apps show as the preview under the subject.
    preheader = f"Your sign-in code is {code}. It works for {minutes} minutes."
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="supported-color-schemes" content="dark">
<title>Your code</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@1,500&family=Manrope:wght@400;600&display=swap" rel="stylesheet">
</head>
<body style="margin:0;padding:0;background:{BG2};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{BG2};">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG2};">
  <tr><td align="center" style="padding:40px 16px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="max-width:440px;background:{BG};border:1px solid {LINE};border-radius:28px;">
      <tr><td style="padding:40px 32px 36px;text-align:center;">

        <div style="font-family:{SERIF};font-style:italic;font-weight:500;font-size:34px;line-height:1;color:{ACCENT};">Knot</div>

        <div style="height:28px;line-height:28px;">&nbsp;</div>

        <div style="font-family:{SANS};font-weight:700;font-size:11px;line-height:1;letter-spacing:2px;text-transform:uppercase;color:{ACCENT};">Your code</div>

        <div style="height:16px;line-height:16px;">&nbsp;</div>

        <table role="presentation" align="center" cellpadding="0" cellspacing="0" border="0"
               style="margin:0 auto;background:{SURFACE};border:1px solid {LINE};border-radius:18px;">
          <tr><td style="padding:18px 22px 18px 32px;font-family:{MONO};font-weight:600;font-size:34px;line-height:1;letter-spacing:10px;color:{INK};">{code}</td></tr>
        </table>

        <div style="height:24px;line-height:24px;">&nbsp;</div>

        <div style="font-family:{SANS};font-size:15px;line-height:1.55;color:{MUTED};">
          It works for {minutes} minutes.<br>
          Type it in, or tap it above your keyboard.
        </div>

      </td></tr>
      <tr><td style="padding:0 32px;"><div style="height:1px;line-height:1px;background:{LINE};">&nbsp;</div></td></tr>
      <tr><td style="padding:20px 32px 26px;text-align:center;font-family:{SANS};font-size:12px;line-height:1.5;color:{MUTED};">
        If you didn't ask for this, you can safely ignore it.
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


async def send_code(to: str, code: str) -> None:
    s = get_settings()
    minutes = s.code_ttl_minutes

    if not s.resend_api_key:
        if s.is_production:
            log.error("RESEND_API_KEY is not set; sign-in codes cannot be sent")
            return
        # Development without Resend: print the code to the uvicorn console instead.
        log.warning("DEV sign-in code for %s: %s", to, code)
        return

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {s.resend_api_key}"},
            json={
                "from": s.mail_from,
                "to": [to],
                "subject": f"Your code: {code}",
                "text": render_text(code, minutes),
                "html": render_html(code, minutes),
            },
        )
    if r.status_code >= 400:
        # Never log the code itself in production; the status is enough to debug.
        log.error("Resend rejected the email: %s %s", r.status_code, r.text[:300])
