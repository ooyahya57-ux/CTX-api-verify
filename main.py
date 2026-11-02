import os
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, jsonify, request
from dotenv import load_dotenv

load_dotenv()
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "database.db"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "8404634986"))
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT", "5000"))

app = Flask(__name__)
db_lock = threading.RLock()


def utc_now():
    return datetime.now(timezone.utc)


def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_lock:
        conn = db_connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS keys (
                    key TEXT PRIMARY KEY,
                    max_devices INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    key TEXT NOT NULL,
                    device TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    PRIMARY KEY (key, device),
                    FOREIGN KEY (key) REFERENCES keys(key) ON DELETE CASCADE
                )
            """)
            conn.commit()
        finally:
            conn.close()


def parse_date(value):
    return datetime.fromisoformat(value)


def key_status(row):
    if not row["active"]:
        return "موقوف"
    if parse_date(row["expires_at"]) <= utc_now():
        return "منتهي"
    return "فعال"


def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or user.id != ADMIN_ID:
            if update.effective_message:
                await update.effective_message.reply_text("⛔ ما عندكش صلاحية الأدمن.")
            return
        return await func(update, context)
    return wrapper


async def telegram_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle commands case-insensitively, including /Key and /DelKey."""
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    raw = (message.text or "").strip()
    if not raw.startswith("/"):
        return

    # Ignore optional @botname suffix.
    parts = raw.split()
    command = parts[0].split("@", 1)[0].lower()
    args = parts[1:]

    if user.id != ADMIN_ID:
        await message.reply_text("⛔ ما عندكش صلاحية الأدمن.")
        return

    if command == "/key":
        if len(args) != 3:
            await message.reply_text("الاستعمال:\n/Key KEY_NAME MAX_DEVICES DAYS\nمثال:\n/Key AKIRA-BOT-JSJSIS 7 30")
            return
        key = args[0].strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{4,80}", key):
            await message.reply_text("❌ صيغة KEY غير صالحة. استعمل الحروف والأرقام و - و _.")
            return
        try:
            max_devices, days = int(args[1]), int(args[2])
            if not (1 <= max_devices <= 10000 and 1 <= days <= 3650):
                raise ValueError()
        except ValueError:
            await message.reply_text("❌ عدد الأجهزة خاصو يكون بين 1 و10000، والأيام بين 1 و3650.")
            return

        expires = (utc_now() + timedelta(days=days)).isoformat()
        created = utc_now().isoformat()
        with db_lock:
            conn = db_connect()
            try:
                conn.execute(
                    "INSERT INTO keys(key,max_devices,expires_at,active,created_at) VALUES(?,?,?,?,?)",
                    (key, max_devices, expires, 1, created)
                )
                conn.commit()
            except sqlite3.IntegrityError:
                await message.reply_text("⚠️ هاد KEY موجود من قبل.")
                return
            finally:
                conn.close()
        await message.reply_text(
            f"✅ تم إنشاء KEY\n"
            f"🔑 `{key}`\n"
            f"👥 عدد الأجهزة: {max_devices}\n"
            f"📅 الصلاحية: {days} يوم",
            parse_mode="Markdown"
        )

    elif command == "/delkey":
        if len(args) != 1:
            await message.reply_text("الاستعمال: /DelKey KEY_NAME")
            return
        with db_lock:
            conn = db_connect()
            try:
                cur = conn.execute("DELETE FROM keys WHERE key=?", (args[0],))
                conn.execute("DELETE FROM devices WHERE key=?", (args[0],))
                conn.commit()
            finally:
                conn.close()
        await message.reply_text("🗑️ تم حذف KEY." if cur.rowcount else "❌ KEY ما لقيتوش.")

    elif command == "/keys":
        with db_lock:
            conn = db_connect()
            try:
                rows = conn.execute("SELECT * FROM keys ORDER BY created_at DESC LIMIT 50").fetchall()
                counts = {
                    r["key"]: conn.execute("SELECT COUNT(*) FROM devices WHERE key=?", (r["key"],)).fetchone()[0]
                    for r in rows
                }
            finally:
                conn.close()
        if not rows:
            await message.reply_text("ما كاين حتى KEY مسجل.")
            return
        lines = ["📋 آخر 50 KEY:"]
        for r in rows:
            lines.append(
                f"\n🔑 {r['key']}\n"
                f"الحالة: {key_status(r)} | الأجهزة: {counts[r['key']]}/{r['max_devices']}\n"
                f"ينتهي: {r['expires_at'][:10]}"
            )
        await message.reply_text("\n".join(lines))

    elif command in ("/disable", "/enable"):
        if len(args) != 1:
            await message.reply_text(f"الاستعمال: {parts[0].split('@')[0]} KEY_NAME")
            return
        active = 0 if command == "/disable" else 1
        with db_lock:
            conn = db_connect()
            try:
                cur = conn.execute("UPDATE keys SET active=? WHERE key=?", (active, args[0]))
                conn.commit()
            finally:
                conn.close()
        if cur.rowcount:
            await message.reply_text("⏸️ تم توقيف KEY." if not active else "▶️ تم تفعيل KEY.")
        else:
            await message.reply_text("❌ KEY ما لقيتوش.")

    elif command == "/check":
        if len(args) != 1:
            await message.reply_text("الاستعمال: /Check KEY_NAME")
            return
        with db_lock:
            conn = db_connect()
            try:
                row = conn.execute("SELECT * FROM keys WHERE key=?", (args[0],)).fetchone()
                count = conn.execute("SELECT COUNT(*) FROM devices WHERE key=?", (args[0],)).fetchone()[0]
            finally:
                conn.close()
        if not row:
            await message.reply_text("❌ KEY غير موجود.")
        else:
            await message.reply_text(
                f"🔑 {row['key']}\nالحالة: {key_status(row)}\n"
                f"الأجهزة: {count}/{row['max_devices']}\n"
                f"ينتهي: {row['expires_at']}"
            )

    elif command == "/start":
        await message.reply_text(
            "مرحبا بالأدمن.\n"
            "/Key KEY_NAME MAX_DEVICES DAYS\n"
            "/DelKey KEY_NAME\n/Keys\n/Check KEY_NAME\n"
            "/Disable KEY_NAME\n/Enable KEY_NAME"
        )


@app.post("/api/verify")
def verify_key():
    data = request.get_json(silent=True) or {}
    key = data.get("key")
    device = data.get("device")

    if not isinstance(key, str) or not isinstance(device, str):
        return jsonify(ok=False, msg="Missing key or device"), 400

    key = key.strip()
    device = device.strip()
    if not key or not device or len(key) > 80 or len(device) > 256:
        return jsonify(ok=False, msg="Invalid key or device"), 400

    with db_lock:
        conn = db_connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM keys WHERE key=?", (key,)).fetchone()
            if not row:
                conn.rollback()
                return jsonify(ok=False, msg="Invalid key"), 401
            if not row["active"]:
                conn.rollback()
                return jsonify(ok=False, msg="Key disabled"), 403
            if parse_date(row["expires_at"]) <= utc_now():
                conn.rollback()
                return jsonify(ok=False, msg="Key expired"), 403

            existing = conn.execute(
                "SELECT 1 FROM devices WHERE key=? AND device=?", (key, device)
            ).fetchone()
            if not existing:
                count = conn.execute(
                    "SELECT COUNT(*) FROM devices WHERE key=?", (key,)
                ).fetchone()[0]
                if count >= row["max_devices"]:
                    conn.rollback()
                    return jsonify(ok=False, msg="Device limit reached"), 403
                conn.execute(
                    "INSERT INTO devices(key,device,first_seen) VALUES(?,?,?)",
                    (key, device, utc_now().isoformat())
                )
            conn.commit()
            return jsonify(ok=True, msg="Key verified successfully"), 200
        except Exception:
            conn.rollback()
            app.logger.exception("Verification error")
            return jsonify(ok=False, msg="Server error"), 500
        finally:
            conn.close()


@app.get("/")
def health():
    return jsonify(status="online", service="Madara Key Verification API")


def run_api():
    app.run(host=API_HOST, port=API_PORT, threaded=True)


def run_bot():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Add it to your .env file.")
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_command))
    # Telegram command entities are handled by this broad text handler too.
    application.add_handler(MessageHandler(filters.COMMAND, telegram_command))
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    init_db()
    # Run API and Telegram polling in separate threads.
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    run_bot()
