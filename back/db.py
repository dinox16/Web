"""MongoDB connector + JSON fallback.

Khi MONGODB_URI chưa được cấu hình (chưa tạo cluster), hệ thống vẫn chạy được
bằng cách lưu users vào back/users.json và OTP vào bộ nhớ tạm.

Khi đã cấu hình MONGODB_URI trong .env -> tự động dùng MongoDB.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

USER_FILE = os.path.join(os.path.dirname(__file__), "users.json")

_client = None
_db = None
_connection_error: Optional[str] = None
_mongo_retry_after_monotonic: float = 0.0
_MONGO_RETRY_COOLDOWN_SEC = 45.0

_otp_lock = threading.Lock()
_otp_memory: Dict[str, Dict[str, Any]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_json_users() -> List[Dict[str, Any]]:
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_json_users(users: List[Dict[str, Any]]) -> None:
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)


def _connect() -> None:
    """Kết nối MongoDB nếu có MONGODB_URI. Bỏ qua nếu chưa cấu hình.

    Lỗi mạng tạm thời không còn chặn thử lại vĩnh viễn (cooldown giữa các lần thử).
    """
    global _client, _db, _connection_error, _mongo_retry_after_monotonic

    if _client is not None:
        return

    uri = (os.environ.get("MONGODB_URI") or "").strip()
    if not uri:
        _db = None
        _connection_error = "MONGODB_URI chưa được cấu hình - dùng JSON fallback"
        return

    now_m = time.monotonic()
    if _mongo_retry_after_monotonic and now_m < _mongo_retry_after_monotonic:
        return

    client_local = None
    try:
        from pymongo import MongoClient
        from pymongo.errors import PyMongoError

        client_local = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client_local.admin.command("ping")
        db_name = os.environ.get("MONGODB_DB", "pfs_db")
        db_local = client_local[db_name]
        try:
            users = db_local[os.environ.get("MONGODB_USERS_COLL", "users")]
            users.create_index("username", unique=True)
            users.create_index("email", unique=True)
            otp_coll = db_local[os.environ.get("MONGODB_OTP_COLL", "otp_codes")]
            otp_coll.create_index("expires_at", expireAfterSeconds=0)
            otp_coll.create_index([("email", 1), ("purpose", 1)])
        except PyMongoError:
            pass
        _client = client_local
        _db = db_local
        client_local = None
        _connection_error = None
        _mongo_retry_after_monotonic = 0.0
    except Exception as e:
        if client_local is not None:
            try:
                client_local.close()
            except Exception:
                pass
        _client = None
        _db = None
        _connection_error = f"Không kết nối được MongoDB: {e}"
        _mongo_retry_after_monotonic = now_m + _MONGO_RETRY_COOLDOWN_SEC


def is_using_mongo() -> bool:
    _connect()
    return _db is not None


def connection_status() -> str:
    _connect()
    if _db is not None:
        return f"MongoDB OK (db={_db.name})"
    return _connection_error or "Chưa cấu hình MongoDB"


# ============ USERS API ============

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    username = (username or "").strip()
    if not username:
        return None
    _connect()
    if _db is not None:
        coll = _db[os.environ.get("MONGODB_USERS_COLL", "users")]
        doc = coll.find_one({"username": username})
        if doc:
            doc.pop("_id", None)
        return doc
    for u in _load_json_users():
        if u.get("username") == username:
            return u
    return None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    email = (email or "").strip().lower()
    if not email:
        return None
    _connect()
    if _db is not None:
        coll = _db[os.environ.get("MONGODB_USERS_COLL", "users")]
        doc = coll.find_one({"email": email})
        if doc:
            doc.pop("_id", None)
        return doc
    for u in _load_json_users():
        if (u.get("email") or "").lower() == email:
            return u
    return None


def create_user(username: str, email: str, password_hash: str) -> bool:
    username = username.strip()
    email = email.strip().lower()
    if get_user_by_username(username) or get_user_by_email(email):
        return False
    doc = {
        "username": username,
        "email": email,
        "passwd": password_hash,
        "created_at": _now().isoformat(),
    }
    _connect()
    if _db is not None:
        coll = _db[os.environ.get("MONGODB_USERS_COLL", "users")]
        try:
            from pymongo.errors import DuplicateKeyError, PyMongoError

            coll.insert_one(dict(doc))
            return True
        except DuplicateKeyError:
            return False
        except PyMongoError:
            return False
    users = _load_json_users()
    users.append(doc)
    _save_json_users(users)
    return True


def update_user_password(email: str, new_password_hash: str) -> bool:
    email = email.strip().lower()
    _connect()
    if _db is not None:
        coll = _db[os.environ.get("MONGODB_USERS_COLL", "users")]
        result = coll.update_one({"email": email}, {"$set": {"passwd": new_password_hash}})
        return result.modified_count > 0
    users = _load_json_users()
    found = False
    for u in users:
        if (u.get("email") or "").lower() == email:
            u["passwd"] = new_password_hash
            found = True
    if found:
        _save_json_users(users)
    return found


# ============ OTP API ============

def save_otp(email: str, code_hash: str, purpose: str, ttl_minutes: int) -> None:
    email = email.strip().lower()
    expires_at = _now() + timedelta(minutes=ttl_minutes)
    _connect()
    if _db is not None:
        coll = _db[os.environ.get("MONGODB_OTP_COLL", "otp_codes")]
        coll.delete_many({"email": email, "purpose": purpose})
        coll.insert_one({
            "email": email,
            "purpose": purpose,
            "code_hash": code_hash,
            "expires_at": expires_at,
            "attempts": 0,
            "created_at": _now(),
        })
        return
    with _otp_lock:
        _otp_memory[f"{email}|{purpose}"] = {
            "code_hash": code_hash,
            "expires_at": expires_at,
            "attempts": 0,
            "created_at": _now(),
        }


def get_otp(email: str, purpose: str) -> Optional[Dict[str, Any]]:
    email = email.strip().lower()
    _connect()
    if _db is not None:
        coll = _db[os.environ.get("MONGODB_OTP_COLL", "otp_codes")]
        doc = coll.find_one({"email": email, "purpose": purpose})
        if doc:
            doc.pop("_id", None)
        return doc
    with _otp_lock:
        return _otp_memory.get(f"{email}|{purpose}")


def increment_otp_attempts(email: str, purpose: str) -> int:
    email = email.strip().lower()
    _connect()
    if _db is not None:
        coll = _db[os.environ.get("MONGODB_OTP_COLL", "otp_codes")]
        doc = coll.find_one_and_update(
            {"email": email, "purpose": purpose},
            {"$inc": {"attempts": 1}},
            return_document=True,
        )
        return doc.get("attempts", 0) if doc else 0
    with _otp_lock:
        key = f"{email}|{purpose}"
        if key in _otp_memory:
            _otp_memory[key]["attempts"] = _otp_memory[key].get("attempts", 0) + 1
            return _otp_memory[key]["attempts"]
    return 0


def delete_otp(email: str, purpose: str) -> None:
    email = email.strip().lower()
    _connect()
    if _db is not None:
        coll = _db[os.environ.get("MONGODB_OTP_COLL", "otp_codes")]
        coll.delete_many({"email": email, "purpose": purpose})
        return
    with _otp_lock:
        _otp_memory.pop(f"{email}|{purpose}", None)
