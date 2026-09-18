import user_data

TITLE = "ติดตามความก้าวหน้า"


def build():
    measurements = user_data.load("measurements", [])
    workouts = user_data.load("progress", {})
    def chart_points(key):
        values = []
        for item in measurements:
            try:
                value = float(item.get(key, ""))
            except (TypeError, ValueError):
                continue
            values.append((item, value))
        if not values:
            return []
        low = min(value for _, value in values)
        high = max(value for _, value in values)
        spread = high - low or 1
        return [
            {"date": item.get("date", ""), "value": value, "position": round(12 + ((value - low) / spread) * 76)}
            for item, value in values
        ]

    return {
        "measurements": measurements,
        "workout_days": sum(1 for done in workouts.values() if done) if isinstance(workouts, dict) else 0,
        "weight_points": chart_points("weight"),
        "height_points": chart_points("height"),
    }


def handle(form):
    measurements = user_data.load("measurements", [])
    if form.get("action") == "delete":
        try:
            index = int(form.get("index", "-1"))
        except ValueError:
            return "รายการที่ต้องการลบไม่ถูกต้อง"
        if 0 <= index < len(measurements):
            measurements.pop(index)
            user_data.save("measurements", measurements)
            return "ลบประวัติการวัดแล้ว"
        return "ไม่พบประวัติการวัดที่ต้องการลบ"
    row = {
        "date": form.get("date", "").strip(),
        "weight": form.get("weight", "").strip(),
        "height": form.get("height", "").strip(),
    }
    if not row["date"] or not row["weight"]:
        return "กรุณากรอกวันที่และน้ำหนัก"
    try:
        if float(row["weight"]) <= 0:
            return "น้ำหนักต้องมากกว่า 0"
    except ValueError:
        return "น้ำหนักต้องเป็นตัวเลข"
    measurements.append(row)
    measurements.sort(key=lambda item: item.get("date", ""))
    user_data.save("measurements", measurements)
    return "บันทึกความก้าวหน้าแล้ว"
