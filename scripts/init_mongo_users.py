#!/usr/bin/env python3
"""Tạo / chuẩn hoá collection `users` trên MongoDB theo cấu trúc đăng ký của project.

Nguồn: `back/db.create_user()` + ràng buộc form/API trong `back/funclogin.py`.

Mỗi document sau khi xác thực OTP:
  {
    "username": str,      # 3–32 ký tự, ^[A-Za-z0-9_.-]+$
    "email": str,         # email (app lưu chữ thường)
    "passwd": str,        # Werkzeug generate_password_hash(...)
    "created_at": str,    # ISO 8601 UTC từ datetime.now(timezone.utc).isoformat()
  }

Chạy từ thư mục gốc repo (có file .env):
  python scripts/init_mongo_users.py

Biến môi trường: MONGODB_URI (bắt buộc), MONGODB_DB, MONGODB_USERS_COLL (xem .env.example).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    uri = (os.environ.get("MONGODB_URI") or "").strip()
    if not uri:
        print("Lỗi: thiếu MONGODB_URI trong .env", file=sys.stderr)
        return 1

    db_name = (os.environ.get("MONGODB_DB") or "pfs_db").strip()
    coll_name = (os.environ.get("MONGODB_USERS_COLL") or "users").strip()

    from pymongo import MongoClient
    from pymongo.errors import OperationFailure, PyMongoError

    # Schema khớp field `db.create_user` — không dùng additionalProperties: false (tránh xung _id)
    validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["username", "email", "passwd", "created_at"],
            "properties": {
                "username": {
                    "bsonType": "string",
                    "minLength": 3,
                    "maxLength": 32,
                    "pattern": "^[A-Za-z0-9_.-]+$",
                    "description": "funclogin.USERNAME_RE",
                },
                "email": {
                    "bsonType": "string",
                    "minLength": 3,
                    "maxLength": 254,
                    "description": "Email; app normalize .lower()",
                },
                "passwd": {
                    "bsonType": "string",
                    "minLength": 1,
                    "description": "Werkzeug password hash",
                },
                "created_at": {
                    "bsonType": "string",
                    "description": "UTC ISO string từ db._now().isoformat()",
                },
            },
        }
    }

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        client.admin.command("ping")
    except PyMongoError as e:
        print(f"Lỗi kết nối MongoDB: {e}", file=sys.stderr)
        return 1

    db = client[db_name]
    names = db.list_collection_names()

    if coll_name not in names:
        try:
            db.create_collection(
                coll_name,
                validator=validator,
                validationLevel="strict",
                validationAction="error",
            )
            print(f"Đã tạo collection {db_name}.{coll_name} (validation strict).")
        except OperationFailure as e:
            print(f"Không tạo được collection: {e}", file=sys.stderr)
            return 1
    else:
        print(f"Collection {db_name}.{coll_name} đã tồn tại — bỏ qua createCollection.")
        try:
            db.command(
                {
                    "collMod": coll_name,
                    "validator": validator,
                    "validationLevel": "strict",
                    "validationAction": "error",
                }
            )
            print("Đã cập nhật validator (collMod).")
        except OperationFailure as e:
            print(
                f"Ghi chú: không áp collMod ({e}). "
                "Có thể do quyền hoặc document cũ không khớp schema — index vẫn được tạo.",
            )

    coll = db[coll_name]
    try:
        coll.create_index("username", unique=True, name="username_unique")
        coll.create_index("email", unique=True, name="email_unique")
    except PyMongoError as e:
        print(f"Lỗi tạo index: {e}", file=sys.stderr)
        return 1

    print("Index unique: username, email (idempotent).")
    print("Hoàn tất.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
