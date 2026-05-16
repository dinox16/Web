"""Login / Register / Forgot password với OTP qua email.

API JSON:
  POST /api/login              {username, passwd}
  POST /api/register/start     {username, email, passwd} -> gửi OTP
  POST /api/register/verify    {email, otp}              -> tạo user thật
  POST /api/forgot/start       {email}                   -> gửi OTP reset
  POST /api/forgot/verify      {email, otp, new_passwd}  -> đổi mật khẩu
  POST /api/otp/resend         {email, purpose}          -> gửi lại OTP
"""

from __future__ import annotations

import os
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .mailer import send_otp_email, smtp_configured

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")

_resend_cooldown: Dict[str, float] = {}


def _ok(data: Dict[str, Any], status: int = 200):
    return jsonify({"ok": True, **data}), status


def _err(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def _generate_otp(length: Optional[int] = None) -> str:
    n = length if length is not None else _otp_expected_length()
    n = max(4, min(int(n), 10))
    return "".join(secrets.choice("0123456789") for _ in range(n))


def _otp_expected_length() -> int:
    try:
        return max(4, min(int(os.environ.get("OTP_LENGTH", "6") or 6), 10))
    except ValueError:
        return 6


def _normalize_otp_digits(otp_raw: str) -> tuple[Optional[str], str]:
    """Chỉ giữ chữ số; OTP phải đúng độ dài cấu hình (OTP_LENGTH)."""
    digits = re.sub(r"\D", "", (otp_raw or "").strip())
    if not digits:
        return None, "Vui lòng nhập mã OTP (chữ số) đúng như trong email đã nhận."
    n = _otp_expected_length()
    if len(digits) != n:
        return None, f"Mã OTP phải đúng {n} chữ số và trùng khớp hoàn toàn với mã trong email."
    return digits, ""


def _resend_remaining_seconds(email: str, purpose: str) -> int:
    cooldown = int(os.environ.get("OTP_RESEND_COOLDOWN", "60") or 60)
    key = f"{email}|{purpose}"
    last = _resend_cooldown.get(key, 0)
    return max(0, int(cooldown - (time.time() - last)))


def _note_otp_sent(email: str, purpose: str) -> None:
    _resend_cooldown[f"{email}|{purpose}"] = time.time()


def _send_otp_for(email: str, purpose: str) -> tuple[bool, str]:
    """Gửi email/console trước; chỉ lưu OTP vào DB khi đã gửi thành công."""
    remaining = _resend_remaining_seconds(email, purpose)
    if remaining > 0:
        return False, f"Vui lòng đợi {remaining}s trước khi yêu cầu mã mới."

    code = _generate_otp()
    sent, send_err = send_otp_email(email, code, purpose=purpose)
    if not sent:
        return False, f"Không gửi được email: {send_err or 'Lỗi SMTP'}"

    code_hash = generate_password_hash(code)
    db.save_otp(email=email, code_hash=code_hash, purpose=purpose, ttl_minutes=_otp_ttl_minutes())
    _note_otp_sent(email, purpose)
    return True, "Đã gửi mã OTP."


def _otp_ttl_minutes() -> int:
    try:
        return int(os.environ.get("OTP_TTL_MINUTES", "10"))
    except ValueError:
        return 10


def _utcnow_naive(dt):
    """Đưa datetime về dạng aware UTC để so sánh."""
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            return datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ============ LOGIN ============

def login():
    if request.method != "POST":
        return _err("Method not allowed", 405)

    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = (data.get("passwd") or data.get("password") or "").strip()

    if not username or not password:
        return _err("Vui lòng nhập tên đăng nhập và mật khẩu.")

    user = db.get_user_by_username(username)
    if not user:
        user = db.get_user_by_email(username)
    if not user or not check_password_hash(user.get("passwd", ""), password):
        return _err("Sai tên đăng nhập hoặc mật khẩu.", 401)

    session["username"] = user["username"]
    session["email"] = user.get("email", "")
    return _ok({"redirect": url_for("dashboard"), "username": user["username"]})


def logout_view():
    session.clear()
    return redirect(url_for("auth"))


# ============ REGISTER (OTP) ============

def register_start():
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = (data.get("passwd") or data.get("password") or "").strip()

    if not USERNAME_RE.match(username):
        return _err("Tên đăng nhập 3-32 ký tự, chỉ chứa chữ/số/._-")
    if not EMAIL_RE.match(email):
        return _err("Email không hợp lệ.")
    if len(password) < 6:
        return _err("Mật khẩu tối thiểu 6 ký tự.")

    if db.get_user_by_username(username):
        return _err("Tên đăng nhập đã tồn tại.")
    if db.get_user_by_email(email):
        return _err("Email đã được sử dụng.")

    session["pending_register"] = {
        "username": username,
        "email": email,
        "passwd_hash": generate_password_hash(password),
    }

    ok, msg = _send_otp_for(email, purpose="register")
    if not ok:
        return _err(msg)
    return _ok({
        "message": msg,
        "email": email,
        "ttl_minutes": _otp_ttl_minutes(),
        "otp_delivered_via": "smtp" if smtp_configured() else "console",
    })


def register_verify():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    otp_input = (data.get("otp") or "").strip()

    pending = session.get("pending_register")
    if not pending or pending.get("email") != email:
        return _err("Phiên đăng ký không hợp lệ. Vui lòng đăng ký lại.")

    err = _verify_otp(email=email, purpose="register", otp_input=otp_input)
    if err:
        return _err(err)

    if not db.create_user(pending["username"], email, pending["passwd_hash"]):
        return _err("Không tạo được tài khoản (đã tồn tại).")

    session.pop("pending_register", None)
    return _ok({"message": "Đăng ký thành công! Hãy đăng nhập.", "username": pending["username"]})


# ============ FORGOT PASSWORD (OTP) ============

def forgot_start():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()

    if not EMAIL_RE.match(email):
        return _err("Email không hợp lệ.")

    user = db.get_user_by_email(email)
    if not user:
        return _err("Không tìm thấy tài khoản với email này.")

    ok, msg = _send_otp_for(email, purpose="reset")
    if not ok:
        return _err(msg)
    session["pending_reset_email"] = email
    return _ok({
        "message": msg,
        "email": email,
        "ttl_minutes": _otp_ttl_minutes(),
        "otp_delivered_via": "smtp" if smtp_configured() else "console",
    })


def forgot_verify():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    otp_input = (data.get("otp") or "").strip()
    new_passwd = (data.get("new_passwd") or data.get("new_password") or "").strip()

    if len(new_passwd) < 6:
        return _err("Mật khẩu mới tối thiểu 6 ký tự.")
    if session.get("pending_reset_email") != email:
        return _err("Phiên đặt lại mật khẩu không hợp lệ.")

    err = _verify_otp(email=email, purpose="reset", otp_input=otp_input)
    if err:
        return _err(err)

    if not db.update_user_password(email, generate_password_hash(new_passwd)):
        return _err("Không cập nhật được mật khẩu.")

    session.pop("pending_reset_email", None)
    return _ok({"message": "Đặt lại mật khẩu thành công! Hãy đăng nhập."})


# ============ RESEND OTP ============

def otp_resend():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    purpose = (data.get("purpose") or "register").strip()

    if purpose not in ("register", "reset"):
        return _err("Loại OTP không hợp lệ.")
    if not EMAIL_RE.match(email):
        return _err("Email không hợp lệ.")

    if purpose == "register":
        pending = session.get("pending_register")
        if not pending or pending.get("email") != email:
            return _err("Phiên đăng ký đã hết. Vui lòng đăng ký lại.")
    else:
        if session.get("pending_reset_email") != email:
            return _err("Phiên đặt lại đã hết. Hãy bắt đầu lại.")

    ok, msg = _send_otp_for(email, purpose=purpose)
    if not ok:
        return _err(msg)
    return _ok({
        "message": msg,
        "ttl_minutes": _otp_ttl_minutes(),
        "otp_delivered_via": "smtp" if smtp_configured() else "console",
    })


# ============ OTP helper ============

def _verify_otp(email: str, purpose: str, otp_input: str) -> str:
    normalized, norm_err = _normalize_otp_digits(otp_input)
    if norm_err:
        return norm_err
    digits = normalized  # chuỗi N chữ số

    record = db.get_otp(email=email, purpose=purpose)
    if not record:
        return "Không tìm thấy mã OTP. Vui lòng nhấn Gửi mã OTP hoặc Gửi lại."

    expires = _utcnow_naive(record.get("expires_at"))
    now_utc = datetime.now(timezone.utc)
    try:
        expired = expires and now_utc > expires
    except TypeError:
        expired = True
    if expired:
        db.delete_otp(email, purpose)
        return "Mã OTP đã hết hạn. Vui lòng yêu cầu mã mới."

    if record.get("attempts", 0) >= 5:
        db.delete_otp(email, purpose)
        return "Bạn đã nhập sai quá nhiều lần. Hãy yêu cầu mã mới."

    if not check_password_hash(record.get("code_hash", ""), digits):
        db.increment_otp_attempts(email, purpose)
        n = _otp_expected_length()
        return f"Mã OTP không khớp. Nhập đúng {n} chữ số giống hệt email/console đã nhận."

    db.delete_otp(email, purpose)
    return ""


# ============ Legacy wrappers (cho route cũ nếu còn ai dùng) ============

def register():
    """Tương thích ngược: trả về JSON tương tự register_start."""
    return register_start()
