"""app.py — GIVEN, DO NOT EDIT.

Turns every file in pages/ into a web page:

    pages/page1.py  →  http://localhost:5000/page1   rendered with templates/page1.html

A page file needs:
    TITLE = "..."                # shown in the menu
    def build():                 # runs on every visit, returns a dict for the template
    def build(query):            # same, but receives the ?a=b URL parameters as a dict
    def handle(form):            # optional, runs when the page's <form method="post"> is sent

Extras the web layer does for you (see docs/tools/flask-page.md):
  - a string returned by handle() becomes the yellow banner on the next page load
  - a "notice" key in build()'s dict is shown as the banner too
  - an uploaded file (<input type="file" name="photo">, form with enctype="multipart/form-data")
    is saved into static/img/ and form["photo"] becomes the saved file name
    (if handle() does not store that name in data.json, the file is removed again)
  - after a POST you are sent back to the same URL you came from (filters survive)
  - a page that is missing, broken, or still a TODO shows a friendly "not built yet" page
Run:  python app.py           (or  python app.py 5001  to pick another port)
"""
import importlib.util
import base64
from datetime import date
import inspect
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
import database
from urllib.parse import urlsplit
from urllib.parse import urlparse

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(HERE, "pages")
UPLOAD_DIR = os.path.join(HERE, "static", "img")
ALLOWED_UPLOAD = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
sys.path.insert(0, HERE)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "fitcalc-development-secret")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024      # 5 MB per upload
USERS_FILE = os.path.join(HERE, "users.json")


def load_local_env():
    """Load simple KEY=value settings without overwriting real environment variables."""
    env_path = os.path.join(HERE, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, encoding="utf-8-sig") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("\"'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


load_local_env()


# ---------- helpers ----------
def read_json(name, default):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_users():
    """Read registered users from the shared SQLite database."""
    return database.read_users()


def save_users(users):
    for username, record in users.items():
        if isinstance(record, dict) and record.get("password"):
            database.create_user(username, record["password"])


def safe_next_url(value):
    """Only allow redirects to a local path after authentication."""
    if not value:
        return url_for("home")
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/") or value.startswith("//"):
        return url_for("home")
    return value


def page_names():
    """page1, page2, ... in order, then everything else, team last."""
    names = [f[:-3] for f in os.listdir(PAGES_DIR) if f.endswith(".py") and not f.startswith("_")]
    numbered = sorted([n for n in names if n.startswith("page") and n[4:].isdigit()], key=lambda n: int(n[4:]))
    others = sorted(n for n in names if n not in numbered and n != "team")
    tail = ["team"] if "team" in names else []
    return numbered + others + tail


def load_page(name):
    """Import pages/<name>.py fresh every time, so edits show up on reload.
    (This also means a variable at the top of a page file does NOT survive between visits —
    keep anything that must persist in data.json.)  Returns (module, error_text)."""
    path = os.path.join(PAGES_DIR, name + ".py")
    if not os.path.exists(path):
        return None, "ไม่พบไฟล์ pages/" + name + ".py"
    try:
        spec = importlib.util.spec_from_file_location("pages." + name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, None
    except Exception:
        return None, traceback.format_exc()


def nav():
    items = []
    for name in page_names():
        module, _ = load_page(name)
        title = getattr(module, "TITLE", None) if module else None
        items.append({"name": name, "title": title or name.capitalize()})
    return items


def save_uploads(files):
    """Save every uploaded file into static/img/ and return {field: saved_name}."""
    saved = {}
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    for field in files:
        f = files[field]
        if not f or not f.filename:
            continue
        base, ext = os.path.splitext(f.filename)
        ext = ext.lower()
        if ext not in ALLOWED_UPLOAD:
            saved[field] = ""          # wrong type → empty string, the page can complain
            continue
        clean = re.sub(r"[^A-Za-z0-9_-]+", "-", base).strip("-")[:40] or "file"
        name = clean + "-" + str(int(time.time())) + ext
        f.save(os.path.join(UPLOAD_DIR, name))
        saved[field] = name
    return saved


def drop_unused_uploads(uploaded):
    """An uploaded file that handle() did not store in data.json (rejected form) is removed again."""
    names = [n for n in uploaded.values() if n]
    if not names:
        return
    try:
        with open(os.path.join(HERE, "data.json"), encoding="utf-8") as f:
            stored = f.read()
    except OSError:
        stored = ""
    try:
        with open(os.path.join(HERE, "fitness_data.json"), encoding="utf-8-sig") as f:
            stored += f.read()
    except OSError:
        pass
    for n in names:
        if n not in stored:
            try:
                os.remove(os.path.join(UPLOAD_DIR, n))
            except OSError:
                pass


def back_to(name, msg=None):
    """Redirect to the page the form came from (keeps ?q=… filters), else to /<name>."""
    target = url_for("page", name=name)
    ref = request.referrer
    if ref:
        parts = urlsplit(ref)
        if parts.path == target:
            target = parts.path + ("?" + parts.query if parts.query else "")
    if msg:
        joiner = "&" if "?" in target else "?"
        target = target + joiner + "msg=" + msg
    return redirect(target)


@app.context_processor
def inject_globals():
    return {
        "nav": nav(),
        "team": read_json("team.json", {"group": {}, "members": []}),
        "msg": request.args.get("msg", ""),
        "current_user": session.get("username"),
    }


def not_built(name, reason, detail=""):
    return render_template("_not_built.html", page=name, reason=reason, detail=detail), 200


# ---------- routes ----------
@app.before_request
def require_login():
    if request.endpoint in {"login", "register", "logout", "static"}:
        return None
    username = session.get("username")
    if not username:
        return redirect(url_for("login", next=request.full_path.rstrip("?")))
    user = read_users().get(username)
    if not user or session.get("auth_version") != user.get("auth_version"):
        session.clear()
        return redirect(url_for("login", next=request.full_path.rstrip("?")))
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.args.get("next", "")
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = read_users().get(username)
        if user and check_password_hash(user.get("password", ""), password):
            session.clear()
            session["username"] = username
            session["auth_version"] = user.get("auth_version", 0)
            return redirect(safe_next_url(request.form.get("next", next_url)))
        error = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
    return render_template("login.html", error=error, next_url=next_url, register_mode=False)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(username) < 3:
            error = "ชื่อผู้ใช้ต้องมีอย่างน้อย 3 ตัวอักษร"
        elif len(password) < 6:
            error = "รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร"
        elif password != confirm:
            error = "รหัสผ่านและการยืนยันรหัสผ่านไม่ตรงกัน"
        else:
            if username in read_users():
                error = "ชื่อผู้ใช้นี้ถูกใช้งานแล้ว"
            else:
                if database.create_user(username, generate_password_hash(password)):
                    session.clear()
                    session["username"] = username
                    return redirect(url_for("home"))
                error = "ไม่สามารถสร้างบัญชีได้ กรุณาลองใหม่"
    return render_template("login.html", error=error, next_url="", register_mode=True)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/account", methods=["GET", "POST"])
def account():
    username = session["username"]
    error = ""
    message = ""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "rename":
            new_username = request.form.get("username", "").strip().lower()
            if len(new_username) < 3:
                error = "ชื่อผู้ใช้ต้องมีอย่างน้อย 3 ตัวอักษร"
            elif new_username != username and new_username in read_users():
                error = "ชื่อผู้ใช้นี้ถูกใช้งานแล้ว"
            elif new_username != username and database.rename_user(username, new_username):
                session["username"] = new_username
                message = "เปลี่ยนชื่อผู้ใช้แล้ว"
            else:
                message = "ชื่อผู้ใช้เหมือนเดิม"
        elif action == "password":
            current = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")
            user = read_users().get(username, {})
            if not check_password_hash(user.get("password", ""), current):
                error = "รหัสผ่านเดิมไม่ถูกต้อง"
            elif len(new_password) < 6:
                error = "รหัสผ่านใหม่ต้องมีอย่างน้อย 6 ตัวอักษร"
            elif new_password != confirm:
                error = "รหัสผ่านใหม่ไม่ตรงกัน"
            else:
                database.update_password(username, generate_password_hash(new_password))
                session.clear()
                return redirect(url_for("login", next="/"))
        elif action == "logout_all":
            database.invalidate_sessions(username)
            session.clear()
            return redirect(url_for("login", msg="ออกจากระบบทุกอุปกรณ์แล้ว"))
        elif action == "delete":
            if request.form.get("confirm") != "ลบบัญชี":
                error = "พิมพ์ ลบบัญชี เพื่อยืนยันการลบ"
            else:
                database.delete_user(username)
                session.clear()
                return redirect(url_for("register"))
    return render_template("account.html", username=session.get("username"), error=error, message=message)


@app.route("/page3/30days", methods=["GET", "POST"])
def workout_30_days():
    import user_data

    if request.method == "POST":
        if request.form.get("action") == "set_duration":
            try:
                duration = max(1, min(int(request.form.get("duration", "30")), 30))
            except ValueError:
                duration = 30
            user_data.save("workout_duration", duration)
            return redirect(url_for("workout_30_days"))
        day = request.form.get("day", "").strip()
        if not day:
            return redirect(url_for("workout_30_days"))
        progress = user_data.load("progress", {})
        progress[day] = request.form.get("done") == "true"
        user_data.save("progress", progress)
        return redirect(url_for("workout_30_days"))

    progress = user_data.load("progress", {})
    duration = user_data.load("workout_duration", 30)
    try:
        duration = max(1, min(int(duration), 30))
    except (TypeError, ValueError):
        duration = 30
    completed_days = sum(1 for day in range(1, duration + 1) if progress.get(str(day)))
    percent = round(completed_days / duration * 100)
    if percent >= 80:
        advice = "ยอดเยี่ยมมาก! รักษาความสม่ำเสมอและพักผ่อนให้เพียงพอ"
    elif percent >= 50:
        advice = "ทำได้ดี! พยายามทำต่อให้ครบตามแผน และอย่าลืมดื่มน้ำ"
    else:
        advice = "เริ่มต้นได้ดี ลองกำหนดเวลาออกกำลังกายให้ชัดเจนเพื่อทำต่อเนื่อง"
    return render_template(
        "page3_30days.html",
        title=f"แผนออกกำลังกาย {duration} วัน",
        plan=[{"day": day, "exercises": [
            user_data.exercise_guide(user_data.BASE_EXERCISES[(day + i) % len(user_data.BASE_EXERCISES)])
            for i in range(5)
        ]} for day in range(1, duration + 1)],
        progress=progress,
        duration=duration,
        completed_days=completed_days,
        progress_percent=percent,
        advice=advice,
    )


@app.route("/")
def home():
    import user_data

    profile = user_data.load("profile", {})
    metrics = {}
    try:
        if all(profile.get(key) for key in ("height", "weight", "age", "gender")):
            metrics = user_data.calculate_metrics(
                profile["height"], profile["weight"], profile["age"],
                profile["gender"], profile.get("activity", "กลาง"), profile.get("goal", "")
            )
    except (TypeError, ValueError, ZeroDivisionError):
        metrics = {}

    today = date.today().isoformat()
    calorie_entries = user_data.load("calories", [])
    dated_entries = [item for item in calorie_entries if isinstance(item, dict) and item.get("date")]
    today_entries = [item for item in dated_entries if item.get("date") == today]
    if not dated_entries:
        today_entries = calorie_entries
    today_calories = sum(int(item.get("calories", 0)) for item in today_entries if isinstance(item, dict))
    measurements = user_data.load("measurements", [])
    latest_measurement = measurements[-1] if measurements else {}
    duration = user_data.load("workout_duration", 30)
    try:
        duration = max(1, min(int(duration), 30))
    except (TypeError, ValueError):
        duration = 30
    progress = user_data.load("progress", {})
    completed_days = sum(1 for day in range(1, duration + 1) if progress.get(str(day)))
    return render_template(
        "home.html",
        dashboard={
            "bmi": metrics.get("bmi"),
            "calories": today_calories,
            "calorie_goal": metrics.get("tdee_adjusted"),
            "calorie_percent": min(100, round(today_calories / metrics["tdee_adjusted"] * 100)) if metrics.get("tdee_adjusted") else 0,
            "workout_percent": round(completed_days / duration * 100),
            "completed_days": completed_days,
            "duration": duration,
            "weight": latest_measurement.get("weight") or profile.get("weight"),
            "goal": profile.get("goal", "ยังไม่ได้เลือก"),
        },
    )


@app.route("/api/analyze-food", methods=["POST"])
def analyze_food():
    """Estimate food and calories with Gemini Vision; the key stays server-side."""
    if not session.get("username"):
        return {"error": "กรุณาเข้าสู่ระบบก่อนใช้งาน"}, 401
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    photo = request.files.get("photo")
    if not api_key:
        return {"error": "ยังไม่ได้ตั้งค่า GEMINI_API_KEY บนเซิร์ฟเวอร์"}, 503
    if not photo or not photo.mimetype.startswith("image/"):
        return {"error": "กรุณาเลือกรูปอาหารที่ถูกต้อง"}, 400
    image_data = photo.read()
    if not image_data or len(image_data) > app.config["MAX_CONTENT_LENGTH"]:
        return {"error": "รูปภาพต้องมีขนาดไม่เกิน 5 MB"}, 400
    prompt = (
        "วิเคราะห์รูปอาหารนี้สำหรับแอปบันทึกแคลอรี่ ตอบเป็น JSON เท่านั้น "
        'รูปแบบ {"food":"ชื่ออาหารภาษาไทย","calories":ตัวเลขจำนวนเต็ม,'
        '"serving":"ปริมาณโดยประมาณภาษาไทย","note":"คำเตือนสั้นๆ"} '
        "หากมองไม่เห็นอาหารให้ food เป็น ไม่ทราบ และ calories เป็น 0 "
        "ให้ประมาณจากปริมาณที่เห็น และระบุว่าเป็นค่าประมาณใน note"
    )
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": photo.mimetype, "data": base64.b64encode(image_data).decode("ascii")}},
            ]
        }],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    request_data = json.dumps(payload).encode("utf-8")
    try:
        api_request = urllib.request.Request(endpoint, data=request_data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(api_request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        analysis = json.loads(text)
        calories = int(analysis.get("calories", 0))
        return {
            "food": str(analysis.get("food", "ไม่ทราบ")),
            "calories": max(0, calories),
            "serving": str(analysis.get("serving", "")),
            "note": str(analysis.get("note", "เป็นค่าประมาณ ควรตรวจสอบก่อนบันทึก")),
        }
    except urllib.error.HTTPError as error:
        try:
            error_body = json.loads(error.read().decode("utf-8"))
            api_message = error_body.get("error", {}).get("message", "")
        except (OSError, ValueError, TypeError):
            api_message = ""
        if error.code in {401, 403}:
            return {"error": "Gemini API key ไม่ถูกต้องหรือไม่มีสิทธิ์ใช้งาน"}, 502
        if error.code == 404:
            return {"error": "ไม่พบโมเดล Gemini ที่ตั้งค่าไว้ กรุณาตรวจสอบ GEMINI_MODEL"}, 502
        return {"error": f"Gemini ปฏิเสธคำขอ{(': ' + api_message) if api_message else ''}"}, 502
    except (urllib.error.URLError, TimeoutError):
        return {"error": "เชื่อมต่อบริการวิเคราะห์อาหารไม่สำเร็จ กรุณาลองใหม่"}, 502
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return {"error": "AI ส่งผลลัพธ์ไม่ถูกต้อง กรุณาลองใช้รูปที่เห็นอาหารชัดขึ้น"}, 502


@app.route("/<name>", methods=["GET", "POST"])
def page(name):
    if name not in page_names():
        return not_built(name, "ไม่มีหน้านี้")

    module, error = load_page(name)
    if error:
        return not_built(name, "ไฟล์ pages/" + name + ".py มีข้อผิดพลาด", error)

    # POST → handle(form) → redirect back (with an optional message)
    if request.method == "POST":
        handler = getattr(module, "handle", None)
        if handler is None:
            return not_built(name, "หน้านี้รับฟอร์มไม่ได้: ยังไม่มี def handle(form) ใน pages/" + name + ".py")
        form = dict(request.form)
        uploaded = save_uploads(request.files)
        form.update(uploaded)
        try:
            result = handler(form)
        except NotImplementedError:
            return not_built(name, "handle() ยังเป็น TODO")
        except Exception:
            return not_built(name, "handle() พัง", traceback.format_exc())
        finally:
            drop_unused_uploads(uploaded)
        if isinstance(result, str) and result:
            return back_to(name, result)
        return back_to(name)

    # GET → build() → template
    builder = getattr(module, "build", None)
    if builder is None:
        return not_built(name, "ยังไม่มี def build() ใน pages/" + name + ".py")
    try:
        if len(inspect.signature(builder).parameters) >= 1:
            query = dict(request.args)
            query.pop("msg", None)
            context = builder(query)
        else:
            context = builder()
    except NotImplementedError:
        return not_built(name, "build() ยังเป็น TODO")
    except Exception:
        return not_built(name, "build() พัง", traceback.format_exc())

    if context is None:
        context = {}
    if not isinstance(context, dict):
        return not_built(name, "build() ต้อง return dict แต่ได้ " + type(context).__name__)

    template = name + ".html"
    if not os.path.exists(os.path.join(HERE, "templates", template)):
        return not_built(name, "ไม่พบไฟล์ templates/" + template)
    try:
        return render_template(template, title=getattr(module, "TITLE", name), page=name, **context)
    except Exception:
        return not_built(name, "templates/" + template + " มีข้อผิดพลาด", traceback.format_exc())


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "").lower() == "true",
        host="0.0.0.0",
        port=port,
    )
