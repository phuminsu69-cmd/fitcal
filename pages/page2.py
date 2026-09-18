import user_data
from datetime import date

TITLE = "บันทึกแคลอรี่ประจำวัน"


def build(query=None):
    entries = user_data.load("calories", [])
    selected_date = (query or {}).get("date", date.today().isoformat())
    if isinstance(selected_date, list):
        selected_date = selected_date[0]
    visible = []
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            continue
        item_date = item.get("date") or selected_date
        if item_date == selected_date:
            visible.append({"item": item, "index": index})
    profile = user_data.load("profile", {})
    goal = None
    try:
        if all(profile.get(key) for key in ("height", "weight", "age", "gender")):
            goal = user_data.calculate_metrics(
                profile["height"], profile["weight"], profile["age"],
                profile["gender"], profile.get("activity", "กลาง"), profile.get("goal", "")
            )["tdee_adjusted"]
    except (TypeError, ValueError, ZeroDivisionError):
        goal = None
    total = sum(int(row["item"].get("calories", 0)) for row in visible)
    remaining = max(0, goal - total) if goal is not None else None
    return {
        "entries": visible, "total": total, "selected_date": selected_date,
        "calorie_goal": goal, "remaining": remaining,
        "calorie_percent": min(100, round(total / goal * 100)) if goal else 0,
        "over_goal": total > goal if goal is not None else False,
    }


def handle(form):
    entries = user_data.load("calories", [])
    action = form.get("action", "")
    if form.get("action") == "delete":
        try:
            index = int(form.get("index", "-1"))
        except ValueError:
            return "รายการที่ต้องการลบไม่ถูกต้อง"
        if 0 <= index < len(entries):
            entries.pop(index)
            user_data.save("calories", entries)
        return "ลบรายการแคลอรี่แล้ว"
    if action == "edit":
        try:
            index = int(form.get("index", "-1"))
        except ValueError:
            return "รายการที่ต้องการแก้ไขไม่ถูกต้อง"
        if not 0 <= index < len(entries):
            return "ไม่พบรายการที่ต้องการแก้ไข"
        food = form.get("food", "").strip()
        meal = form.get("meal", "").strip()
        calories = form.get("calories", "").strip()
        if not food or not calories:
            return "กรุณากรอกชื่ออาหารและแคลอรี่"
        try:
            calories_value = int(calories)
        except ValueError:
            return "แคลอรี่ต้องเป็นตัวเลข"
        if calories_value < 0:
            return "แคลอรี่ต้องไม่ติดลบ"
        entries[index].update({"food": food, "meal": meal, "calories": calories_value, "date": form.get("date", date.today().isoformat())})
        user_data.save("calories", entries)
        return "แก้ไขรายการอาหารแล้ว"
    food = form.get("food", "").strip()
    calories = form.get("calories", "").strip()
    meal = form.get("meal", "").strip()
    if not food or not calories:
        return "กรุณากรอกชื่ออาหารและแคลอรี่"
    try:
        calories_value = int(calories)
    except ValueError:
        return "แคลอรี่ต้องเป็นตัวเลข"
    if calories_value < 0:
        return "แคลอรี่ต้องไม่ติดลบ"
    entries.append({"food": food, "calories": calories_value, "meal": meal, "date": form.get("date", date.today().isoformat())})
    user_data.save("calories", entries)
    return "บันทึกแคลอรี่แล้ว"
