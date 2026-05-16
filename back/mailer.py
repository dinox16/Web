"""Gửi email OTP qua SMTP.

Nếu chưa điền SMTP_USERNAME / SMTP_PASSWORD, email **không** được gửi;
mã OTP vẫn in ra terminal (chạy `python app.py`) để dev test — không dùng cho production.

`funclogin._send_otp_for` chỉ lưu mã vào DB **sau** khi bước gửi thành công
(hoặc sau khi in console ở chế độ dev).
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional


def smtp_configured() -> bool:
    """Đã có username/password SMTP để gửi mail thật."""
    return bool(os.environ.get("SMTP_USERNAME") and os.environ.get("SMTP_PASSWORD"))


def send_otp_email(to_email: str, otp_code: str, purpose: str = "register") -> tuple[bool, Optional[str]]:
    """Trả về (success, error_message).

    - SMTP đủ cấu hình → gửi mail thật.
    - Chưa có SMTP → in mã ra stdout, vẫn trả (True, None) để luồng dev tiếp tục.
    """
    purpose_text = {
        "register": "đăng ký tài khoản",
        "reset": "đặt lại mật khẩu",
    }.get(purpose, "xác thực tài khoản")

    subject = f"[Program For Student] Mã OTP {purpose_text}"
    body_text = (
        f"Xin chào,\n\n"
        f"Mã OTP của bạn cho yêu cầu {purpose_text} là: {otp_code}\n"
        f"Mã có hiệu lực trong {os.environ.get('OTP_TTL_MINUTES', '10')} phút.\n\n"
        f"Nếu bạn không yêu cầu mã này, vui lòng bỏ qua email.\n\n"
        f"-- Program For Student"
    )
    body_html = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:520px;margin:auto;padding:24px;border-radius:14px;background:#f7faff;border:1px solid #e0e8f5;">
      <h2 style="color:#1976d2;margin:0 0 10px 0;">Program For Student</h2>
      <p>Xin chào,</p>
      <p>Mã OTP dùng để <b>{purpose_text}</b> của bạn là:</p>
      <div style="font-size:28px;font-weight:700;letter-spacing:8px;background:#fff;border:2px dashed #1976d2;color:#1250a3;padding:14px 0;text-align:center;border-radius:10px;margin:14px 0;">{otp_code}</div>
      <p>Mã có hiệu lực trong <b>{os.environ.get('OTP_TTL_MINUTES', '10')}</b> phút.</p>
      <p style="color:#666;font-size:0.9rem;">Nếu bạn không yêu cầu mã này, vui lòng bỏ qua email này.</p>
      <hr style="border:none;border-top:1px solid #e0e8f5;"/>
      <p style="color:#888;font-size:0.85rem;margin:0;">-- Program For Student --</p>
    </div>
    """

    if not smtp_configured():
        print("=" * 60)
        print(f"[DEV-OTP] To: {to_email} | Purpose: {purpose} | Code: {otp_code}")
        print("(Chưa cấu hình SMTP — không gửi email; chỉ có mã ở terminal này.)")
        print("=" * 60)
        return True, None

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("MAIL_FROM", os.environ["SMTP_USERNAME"])
    msg["To"] = to_email
    msg.set_content(body_text)
    msg.add_alternative(body_html, subtype="html")

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

    try:
        if use_tls:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context()) as server:
                server.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
                server.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)
