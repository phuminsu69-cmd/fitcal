"""Firebase Realtime Database storage used by the Flask application."""
import base64
import json
import os
import tempfile
from threading import Lock

import firebase_admin
from firebase_admin import credentials, db

_lock = Lock()
_app = None
_reference = None


def _load_env():
    values = {}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(path, encoding="utf-8-sig") as source:
            for line in source:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip("\"'")
    except OSError:
        pass
    for key in ("FIREBASE_DATABASE_URL", "FIREBASE_SERVICE_ACCOUNT"):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def _username_key(username):
    return base64.urlsafe_b64encode(username.encode("utf-8")).decode("ascii").rstrip("=")


def reference():
    global _app, _reference
    if _reference is not None:
        return _reference
    settings = _load_env()
    url = settings.get("FIREBASE_DATABASE_URL")
    service_account = settings.get("FIREBASE_SERVICE_ACCOUNT")
    service_account_json = settings.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if not url:
        return None
    if service_account and not os.path.isabs(service_account):
        service_account = os.path.join(os.path.dirname(os.path.abspath(__file__)), service_account)
    if service_account and not os.path.exists(service_account):
        raise RuntimeError("ไม่พบไฟล์ Firebase service account: " + service_account)
    with _lock:
        if _reference is None:
            if not firebase_admin._apps:
                options = {"databaseURL": url.rstrip("/")}
                if service_account_json:
                    try:
                        app_credentials = credentials.Certificate(json.loads(service_account_json))
                    except (TypeError, ValueError, json.JSONDecodeError) as error:
                        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON ไม่ใช่ JSON ที่ถูกต้อง") from error
                else:
                    app_credentials = credentials.Certificate(service_account) if service_account else None
                _app = firebase_admin.initialize_app(app_credentials, options)
            else:
                _app = firebase_admin.get_app()
            _reference = db.reference("/", app=_app)
    return _reference


def enabled():
    return reference() is not None


def _user_path(username):
    return reference().child("users").child(_username_key(username))


def migrate(users, user_data):
    root = reference()
    if root is None:
        return
    existing = root.child("users").get()
    if existing:
        return
    for username, record in users.items():
        root.child("users").child(_username_key(username)).set({
            "username": username,
            "password": record["password"],
            "auth_version": int(record.get("auth_version", 0)),
            "data": user_data.get(username, {}),
        })


def read_users():
    root = reference()
    if root is None:
        return None
    records = root.child("users").get() or {}
    return {
        record["username"]: {
            "password": record.get("password", ""),
            "auth_version": int(record.get("auth_version", 0)),
        }
        for record in records.values()
        if isinstance(record, dict) and record.get("username")
    }


def create_user(username, password_hash):
    path = _user_path(username)
    if path.get() is not None:
        return False
    path.set({"username": username, "password": password_hash, "auth_version": 0, "data": {}})
    return True


def rename_user(old_username, new_username):
    old_path = _user_path(old_username)
    new_path = _user_path(new_username)
    if old_path.get() is None or new_path.get() is not None:
        return False
    record = old_path.get()
    record["username"] = new_username
    new_path.set(record)
    old_path.delete()
    return True


def update_password(username, password_hash):
    path = _user_path(username)
    record = path.get()
    if record is None:
        return
    path.update({"password": password_hash, "auth_version": int(record.get("auth_version", 0)) + 1})


def invalidate_sessions(username):
    path = _user_path(username)
    record = path.get()
    if record is not None:
        path.update({"auth_version": int(record.get("auth_version", 0)) + 1})


def delete_user(username):
    _user_path(username).delete()


def load_user_data(username):
    if reference() is None:
        return None
    record = _user_path(username).get() or {}
    return record.get("data", {}) if isinstance(record.get("data", {}), dict) else {}


def save_user_data(username, key, value):
    _user_path(username).child("data").child(key).set(value)
