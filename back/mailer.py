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
    """Đã có username/password SMTP để gửi mail thật (không rỗng / không chỉ khoảng trắng)."""
    u = (os.environ.get("SMTP_USERNAME") or "").strip()
    p = (os.environ.get("SMTP_PASSWORD") or "").strip()
    return bool(u and p)


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
        print()
        print("  → Chưa gửi email: thiếu SMTP_USERNAME hoặc SMTP_PASSWORD trong .env")
        print("  → Để nhận OTP qua Gmail: https://myaccount.google.com/apppasswords")
        print("     rồi điền SMTP_USERNAME, SMTP_PASSWORD, MAIL_FROM trong .env và chạy lại app.")
        print("  → Dùng mã trên dòng [DEV-OTP] để nhập vào trang đăng ký (chế độ dev).")
        print("=" * 60)
        return True, None

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("MAIL_FROM", os.environ["SMTP_USERNAME"])
    msg["To"] = to_email
    msg.set_content(body_text)
    msg.add_alternative(body_html, subtype="html")

    host = (os.environ.get("SMTP_HOST") or "smtp.gmail.com").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    ctx = ssl.create_default_context()

    # Cổng 465 = SMTP over SSL ngay (SMTPS). KHÔNG dùng STARTTLS sau khi đã vào plaintext.
    # Cổng 587 (Gmail,...): plaintext → STARTTLS.
    use_starttls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    tls_mode = (os.environ.get("SMTP_TLS_MODE") or "").strip().lower()
    if tls_mode in ("ssl", "smtps"):
        implicit_ssl = True
    elif tls_mode in ("starttls", "tls-upgrade"):
        implicit_ssl = False
    elif port == 465:
        implicit_ssl = True
    else:
        implicit_ssl = not use_starttls

    try:
        user = os.environ["SMTP_USERNAME"].strip()
        pwd = os.environ["SMTP_PASSWORD"].strip()

        if implicit_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=20, context=ctx) as server:
                server.login(user, pwd)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(user, pwd)
                server.send_message(msg)
        return True, None
    except ssl.SSLError as e:
        hint = ""
        low = str(e).lower()
        if "wrong_version" in low or "wrong_ssl" in low:
            hint = (
                " Kiểm tra .env: cổng 587 + SMTP_USE_TLS=true (STARTTLS); "
                "hoặc cổng 465 — app đã dùng SMTP_SSL tự động."
            )
        return False, str(e) + hint
    except Exception as e:
        return False, str(e)