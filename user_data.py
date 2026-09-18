import json
import os
import database

from flask import session

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "fitness_data.json")
BASE_EXERCISES = [
    "Push-ups (วิดพื้น)", "Squats (สควอต)", "Plank (แพลงก์)",
    "Jumping Jacks (กระโดดตบ)", "Burpees (เบอร์พี)",
    "Lunges (เดินงอต้นขา)", "Mountain Climbers (ปีนเขา)",
    "Bicycle Crunches (ซิทอัพปั่นจักรยาน)", "Side Plank (แพลงก์ด้านข้าง)",
    "Leg Raises (ยกขา)", "Pull-ups (ดึงข้อ)", "Dips (ดิปส์)",
    "Shoulder Taps (ตบไหล่)", "Glute Bridge (สะพานสะโพก)",
    "Wall Sit (นั่งพิงผนัง)",
]
EXERCISE_GUIDES = {
    "Push-ups (วิดพื้น)": {
        "steps": ["วางมือกว้างกว่าหัวไหล่เล็กน้อย", "เกร็งลำตัวให้เป็นเส้นตรง", "ย่อตัวจนอกเกือบแตะพื้น แล้วดันกลับ"],
        "tip": "หายใจเข้าตอนย่อตัว และหายใจออกตอนดันตัวขึ้น",
        "query": "วิธีทำ Push ups วิดพื้น สำหรับมือใหม่",
    },
    "Squats (สควอต)": {
        "steps": ["ยืนแยกเท้ากว้างประมาณหัวไหล่", "ดันสะโพกไปด้านหลังและย่อเข่า", "ดันส้นเท้ากลับขึ้น โดยให้เข่าอยู่แนวเดียวกับปลายเท้า"],
        "tip": "หลังตรงและอย่าให้เข่าหุบเข้าด้านใน",
        "query": "วิธีทำ Squats สควอต ที่ถูกต้อง",
    },
    "Plank (แพลงก์)": {
        "steps": ["วางศอกใต้หัวไหล่และเหยียดขา", "เกร็งหน้าท้องและสะโพกให้ลำตัวตรง", "ค้างท่าโดยไม่กลั้นหายใจ"],
        "tip": "อย่ายกสะโพกสูงหรือแอ่นหลัง",
        "query": "วิธีทำ Plank แพลงก์ ที่ถูกต้อง",
    },
}
EXERCISE_GUIDE_IMAGES = {
    "Push-ups (วิดพื้น)": "https://encrypted-tbn1.gstatic.com/licensed-image?q=tbn:ANd9GcTT2Gc2LCfAAvGT-eKtxSFJ3f4TMN7HORFEWyuVjsWhUxRKzIXnmLwnCWM34L2KStPTFx1pqtKgIu8UO5Y",
    "Squats (สควอต)": "https://encrypted-tbn1.gstatic.com/licensed-image?q=tbn:ANd9GcTLspDrPg1mmfEgV5TvPr4zO-J_Su2gdYOaSuFwdLWfgdeEyPzm7RfJYmGWW7eRg4Fy3iIIqnjegUzD-d8",
    "Plank (แพลงก์)": "https://encrypted-tbn1.gstatic.com/licensed-image?q=tbn:ANd9GcSXBRCtdFnaxEHGk0XHbHiOYa5Q81lPXhicynTLDaJAsb7sxYYMbT8jCJCZlw9XIRVGI0AAppRyybRErrg",
    "Jumping Jacks (กระโดดตบ)": "https://encrypted-tbn1.gstatic.com/licensed-image?q=tbn:ANd9GcQ10_hhBwL2mipmRRsH4Y3IA4ZmNRnBw2uAHi91S2g2vL5njkL9QN1zKBaI1rtQaZTr8BeZL2VFmMXKPEY",
    "Burpees (เบอร์พี)": "https://encrypted-tbn1.gstatic.com/licensed-image?q=tbn:ANd9GcQ10_hhBwL2mipmRRsH4Y3IA4ZmNRnBw2uAHi91S2g2vL5njkL9QN1zKBaI1rtQaZTr8BeZL2VFmMXKPEY",
    "Lunges (เดินงอต้นขา)": "https://encrypted-tbn2.gstatic.com/licensed-image?q=tbn:ANd9GcTFmubagqEY_CqNsi5DSgCyelYlM-Ea9YNPoBI2NjfCjNoDMMoYjT0KuvtALqAlGID8epS2sRPryKVZAzc",
    "Mountain Climbers (ปีนเขา)": "https://encrypted-tbn2.gstatic.com/licensed-image?q=tbn:ANd9GcSOrc120cD1Aez4SGndQFAlp66d78feax9VOJyBAoXSt2aUS19mxsCqIJBbV7P2yAIAQ_q6y2uUxxW7-24",
    "Bicycle Crunches (ซิทอัพปั่นจักรยาน)": "https://encrypted-tbn3.gstatic.com/licensed-image?q=tbn:ANd9GcQMQqr9Z9BqanhFytl9uXGwKuL_Sb4MS4K-PRhHvD6jXgrUKrvc3bHk5W5OM5NEbw6v-UKv0s-83tTK3Ro",
    "Side Plank (แพลงก์ด้านข้าง)": "https://encrypted-tbn1.gstatic.com/licensed-image?q=tbn:ANd9GcSsMqhzuz-krZgEg7JGP5Nw0N_8X9E-oST8yRm_jxSFJw_QivH-cDH5GgDm-Mkf7v32N98SbPih8lMhlCU",
    "Leg Raises (ยกขา)": "https://encrypted-tbn1.gstatic.com/licensed-image?q=tbn:ANd9GcQtWCu8ogVuQpPG1wkiMMTOP7Awe-zne7OLnlpFAakyj3frKc0UVr83O0fbtHf498Ngm83Qm9jsSCPJWsg",
    "Pull-ups (ดึงข้อ)": "https://encrypted-tbn1.gstatic.com/licensed-image?q=tbn:ANd9GcTjfwJZMNtfhM8TqmGnk63kyIXFfSlELsItqeRtXLWDgHPs6Rl6HhrQHN_W904dCRUIE18VUWWjP-dj1lU",
    "Dips (ดิปส์)": "https://encrypted-tbn1.gstatic.com/licensed-image?q=tbn:ANd9GcQrZC31L-PKr08XNgqBMBG0iD5QRIcOq4IXShaLjlSgZQW6l6o6tZP6zyfXsEQDeozrQPIyb4eMxkPU7TY",
    "Shoulder Taps (ตบไหล่)": "https://encrypted-tbn1.gstatic.com/licensed-image?q=tbn:ANd9GcRcygEpZsozfPl_9bXRxfUpiYWmeTZTM3D1YaCcIae3dKv4HxrrYl__hab8iatR6EZCMHRipqZMTkBWyTk",
    "Glute Bridge (สะพานสะโพก)": "https://encrypted-tbn2.gstatic.com/licensed-image?q=tbn:ANd9GcQDG9r3LUfZ5gDQXHh3yxwozH-EMY72tx4idLdoUGQ81My2O0H6i6zWgvowmDzI8aIFGpDF_OlUJQpkbC8",
    "Wall Sit (นั่งพิงผนัง)": "https://encrypted-tbn2.gstatic.com/licensed-image?q=tbn:ANd9GcTOeJQQuXc3NYgQElLC5Sl-tET8C9WhdA05pFPrvieaHom-UiKTzUqzlQmP8OL9sVg0b5QDE_uYOU5o_k8",
}


def exercise_guide(name):
    guide = EXERCISE_GUIDES.get(name, {
        "steps": ["จัดท่าให้มั่นคงและเกร็งแกนกลางลำตัว", "เคลื่อนไหวช้า ๆ ตามจังหวะที่ควบคุมได้", "กลับสู่ท่าเริ่มต้นแล้วทำซ้ำ"],
        "tip": "หยุดทันทีหากมีอาการเจ็บผิดปกติ",
        "query": f"วิธีทำ {name}",
    })
    return {"name": name, "img": EXERCISE_GUIDE_IMAGES.get(name, ""), **guide}


def _all_data():
    username = session.get("username")
    if not username:
        return {}
    return {username: database.load_user_data(username)}


def load(key, default):
    username = session.get("username")
    if not username:
        return default
    user = database.load_user_data(username)
    value = user.get(key, default) if isinstance(user, dict) else default
    if key == "calories" and key not in user and isinstance(user, dict):
        legacy_logs = user.get("calorie_logs", {})
        value = []
        if isinstance(legacy_logs, dict):
            for logged_date, entries in legacy_logs.items():
                if not isinstance(entries, list):
                    continue
                for item in entries:
                    if isinstance(item, dict):
                        converted = dict(item)
                        converted.setdefault("date", logged_date)
                        value.append(converted)
    return value if isinstance(value, type(default)) else default


def save(key, value):
    username = session.get("username")
    if not username:
        raise RuntimeError("ต้องเข้าสู่ระบบก่อนบันทึกข้อมูล")
    database.save_user_data(username, key, value)


def calculate_metrics(height, weight, age, sex, activity, goal):
    height = float(height)
    weight = float(weight)
    age = int(age)
    bmi = round(weight / (height / 100) ** 2, 2)
    bmr = round(10 * weight + 6.25 * height - 5 * age + (5 if sex == "ชาย" else -161))
    factor = {"ต่ำ": 1.2, "กลาง": 1.55, "สูง": 1.9}.get(activity, 1.55)
    tdee = round(bmr * factor)
    adjusted = tdee - 500 if goal == "ลดน้ำหนัก" else tdee + 400 if goal == "เพิ่มกล้ามเนื้อ" else tdee
    return {"bmi": bmi, "bmr": bmr, "tdee": tdee, "tdee_adjusted": adjusted}


def exercise_plan(duration):
    duration = max(1, min(int(duration), 30))
    return [
        {"day": day, "exercises": [
            exercise_guide(BASE_EXERCISES[(day + i) % len(BASE_EXERCISES)])
            for i in range(5)
        ]}
        for day in range(1, duration + 1)
    ]
