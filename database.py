"""SQLite storage for accounts and per-user fitness data."""
import json
import os
import sqlite3
import firebase_storage

HERE = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(HERE, "fitcalc.db")


def connect():
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize():
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                auth_version INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS user_data (
                username TEXT NOT NULL,
                data_key TEXT NOT NULL,
                data_value TEXT NOT NULL,
                PRIMARY KEY (username, data_key),
                FOREIGN KEY (username) REFERENCES users(username)
            );
            """
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        if "auth_version" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 0")
        migrate_json(connection)
        users = {
            row["username"]: {"password": row["password"], "auth_version": row["auth_version"]}
            for row in connection.execute("SELECT username, password, auth_version FROM users")
        }
        data = {}
        for row in connection.execute("SELECT username, data_key, data_value FROM user_data"):
            data.setdefault(row["username"], {})[row["data_key"]] = json.loads(row["data_value"])
        firebase_storage.migrate(users, data)


def migrate_json(connection):
    """Import legacy JSON files once, while leaving them as a local backup."""
    user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    users_path = os.path.join(HERE, "users.json")
    data_path = os.path.join(HERE, "fitness_data.json")
    if user_count == 0 and os.path.exists(users_path):
        with open(users_path, encoding="utf-8-sig") as source:
            users = json.load(source)
        for username, record in users.items():
            if isinstance(record, dict) and record.get("password"):
                connection.execute(
                    "INSERT OR IGNORE INTO users(username, password) VALUES (?, ?)",
                    (username, record["password"]),
                )
    if not os.path.exists(data_path):
        return
    with open(data_path, encoding="utf-8-sig") as source:
        data = json.load(source)
    for username, values in data.items():
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            connection.execute(
                "INSERT OR IGNORE INTO user_data(username, data_key, data_value) VALUES (?, ?, ?)",
                (username, key, json.dumps(value, ensure_ascii=False)),
            )


def read_users():
    remote = firebase_storage.read_users()
    if remote is not None:
        return remote
    with connect() as connection:
        rows = connection.execute("SELECT username, password, auth_version FROM users").fetchall()
    return {row["username"]: {"password": row["password"], "auth_version": row["auth_version"]} for row in rows}


def create_user(username, password_hash):
    if firebase_storage.enabled():
        return firebase_storage.create_user(username, password_hash)
    with connect() as connection:
        try:
            connection.execute(
                "INSERT INTO users(username, password) VALUES (?, ?)",
                (username, password_hash),
            )
        except sqlite3.IntegrityError:
            return False
    return True


def rename_user(old_username, new_username):
    if firebase_storage.enabled():
        return firebase_storage.rename_user(old_username, new_username)
    with connect() as connection:
        try:
            connection.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, old_username))
            connection.execute("UPDATE user_data SET username = ? WHERE username = ?", (new_username, old_username))
        except sqlite3.IntegrityError:
            return False
    return True


def update_password(username, password_hash):
    if firebase_storage.enabled():
        firebase_storage.update_password(username, password_hash)
        return
    with connect() as connection:
        connection.execute(
            "UPDATE users SET password = ?, auth_version = auth_version + 1 WHERE username = ?",
            (password_hash, username),
        )


def invalidate_sessions(username):
    if firebase_storage.enabled():
        firebase_storage.invalidate_sessions(username)
        return
    with connect() as connection:
        connection.execute("UPDATE users SET auth_version = auth_version + 1 WHERE username = ?", (username,))


def delete_user(username):
    if firebase_storage.enabled():
        firebase_storage.delete_user(username)
        return
    with connect() as connection:
        connection.execute("DELETE FROM user_data WHERE username = ?", (username,))
        connection.execute("DELETE FROM users WHERE username = ?", (username,))


def load_user_data(username):
    remote = firebase_storage.load_user_data(username)
    if remote is not None:
        return remote
    with connect() as connection:
        rows = connection.execute(
            "SELECT data_key, data_value FROM user_data WHERE username = ?", (username,)
        ).fetchall()
    return {row["data_key"]: json.loads(row["data_value"]) for row in rows}


def save_user_data(username, key, value):
    if firebase_storage.enabled():
        firebase_storage.save_user_data(username, key, value)
        return
    encoded = json.dumps(value, ensure_ascii=False)
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO user_data(username, data_key, data_value) VALUES (?, ?, ?)
            ON CONFLICT(username, data_key) DO UPDATE SET data_value = excluded.data_value
            """,
            (username, key, encoded),
        )


initialize()
