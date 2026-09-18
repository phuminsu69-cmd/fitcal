import user_data

TITLE = "ข้อมูลส่วนตัว"


def visual_reference(age, gender):
    """Return an approximate BMI midpoint for the body preview comparison."""
    age = int(age)
    if age < 18:
        points = [(5, 15.5), (10, 16.5), (13, 18.0), (17, 21.0)]
        if gender == "หญิง":
            points = [(year, value + 0.2) for year, value in points]
        if age <= points[0][0]:
            return points[0][1]
        for (left_age, left_bmi), (right_age, right_bmi) in zip(points, points[1:]):
            if age <= right_age:
                ratio = (age - left_age) / (right_age - left_age)
                return round(left_bmi + ratio * (right_bmi - left_bmi), 1)
        return points[-1][1]
    return 21.7


def build():
    profile = user_data.load("profile", {})
    metrics = {}
    try:
        if all(profile.get(key) for key in ("height", "weight", "age", "gender")):
            metrics = user_data.calculate_metrics(
                profile["height"], profile["weight"], profile["age"],
                profile["gender"], profile.get("activity", "กลาง"), profile.get("goal", "")
            )
            metrics["reference_bmi"] = visual_reference(profile["age"], profile["gender"])
            metrics["body_ratio"] = round(max(0.78, min(1.42, metrics["bmi"] / metrics["reference_bmi"])), 2)
            metrics["height_ratio"] = round(max(0.86, min(1.14, float(profile["height"]) / 170)), 2)
            metrics["body_comparison"] = (
                "ใกล้เคียงหุ่นมาตรฐาน" if abs(metrics["bmi"] - metrics["reference_bmi"]) < 2
                else "ใหญ่กว่าหุ่นมาตรฐาน" if metrics["bmi"] > metrics["reference_bmi"]
                else "เล็กกว่าหุ่นมาตรฐาน"
            )
    except (TypeError, ValueError, ZeroDivisionError):
        metrics = {}
    return {"profile": profile, "metrics": metrics}


def handle(form):
    goals = {"ลดน้ำหนัก", "เพิ่มกล้ามเนื้อ", "รักษาน้ำหนัก", "เพิ่มความฟิต"}
    activities = {"ต่ำ", "กลาง", "สูง"}
    profile = {
        "name": form.get("name", "").strip(),
        "age": form.get("age", "").strip(),
        "gender": form.get("gender", "").strip(),
        "height": form.get("height", "").strip(),
        "weight": form.get("weight", "").strip(),
        "goal": form.get("goal", "").strip(),
        "activity": form.get("activity", "กลาง").strip(),
    }
    if not profile["name"]:
        return "กรุณากรอกชื่อ"
    if profile["goal"] not in goals:
        return "กรุณาเลือกเป้าหมายที่ต้องการ"
    if profile["activity"] not in activities:
        return "กรุณาเลือกระดับกิจกรรม"
    user_data.save("profile", profile)
    return "บันทึกข้อมูลส่วนตัวเรียบร้อยแล้ว"
