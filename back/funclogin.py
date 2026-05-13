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
from typing import Any, Dict

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .mailer import send_otp_email

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")

_resend_cooldown: Dict[str, float] = {}


def _ok(data: Dict[str, Any], status: int = 200):
    return jsonify({"ok": True, **data}), status


def _err(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def _generate_otp(length: int = 6) -> str:
    length = max(4, min(int(length or 6), 10))
    return "".join(secrets.choice("0123456789") for _ in range(length))


def _otp_ttl_minutes() -> int:
    try:
        return int(os.environ.get("OTP_TTL_MINUTES", "10"))
    except ValueError:
        return 10


def _check_resend(email: str, purpose: str) -> tuple[bool, int]:
    cooldown = int(os.environ.get("OTP_RESEND_COOLDOWN", "60") or 60)
    key = f"{email}|{purpose}"
    last = _resend_cooldown.get(key, 0)
    remaining = int(cooldown - (time.time() - last))
    if remaining > 0:
        return False, remaining
    _resend_cooldown[key] = time.time()
    return True, 0


def _utcnow_naive(dt):
    """Đưa datetime về dạng aware UTC để so sánh."""
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            return datetime.fromisoformat(dt)
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _send_otp_for(email: str, purpose: str) -> tuple[bool, str]:
    ok_cooldown, remaining = _check_resend(email, purpose)
    if not ok_cooldown:
        return False, f"Vui lòng đợi {remaining}s trước khi yêu cầu mã mới."

    code = _generate_otp(int(os.environ.get("OTP_LENGTH", "6") or 6))
    code_hash = generate_password_hash(code)
    db.save_otp(email=email, code_hash=code_hash, purpose=purpose, ttl_minutes=_otp_ttl_minutes())

    sent, err = send_otp_email(email, code, purpose=purpose)
    if not sent:
        return False, f"Không gửi được email: {err}"
    return True, "Đã gửi mã OTP."


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
    return _ok({"message": msg, "email": email, "ttl_minutes": _otp_ttl_minutes()})


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
    return _ok({"message": msg, "email": email, "ttl_minutes": _otp_ttl_minutes()})


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
    return _ok({"message": msg, "ttl_minutes": _otp_ttl_minutes()})


# ============ OTP helper ============

def _verify_otp(email: str, purpose: str, otp_input: str) -> str:
    if not otp_input or not otp_input.isdigit():
        return "Mã OTP không hợp lệ."

    record = db.get_otp(email=email, purpose=purpose)
    if not record:
        return "Không tìm thấy mã OTP. Vui lòng yêu cầu mã mới."

    expires = _utcnow_naive(record.get("expires_at"))
    if expires and datetime.now(timezone.utc) > expires:
        db.delete_otp(email, purpose)
        return "Mã OTP đã hết hạn. Vui lòng yêu cầu mã mới."

    if record.get("attempts", 0) >= 5:
        db.delete_otp(email, purpose)
        return "Bạn đã nhập sai quá nhiều lần. Hãy yêu cầu mã mới."

    if not check_password_hash(record.get("code_hash", ""), otp_input):
        db.increment_otp_attempts(email, purpose)
        return "Mã OTP không đúng."

    db.delete_otp(email, purpose)
    return ""


# ============ Legacy wrappers (cho route cũ nếu còn ai dùng) ============

def register():
    """Tương thích ngược: trả về JSON tương tự register_start."""
    return register_start()
