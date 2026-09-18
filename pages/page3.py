import user_data

TITLE = "ตารางออกกำลังกาย"


def build():
    guides = [user_data.exercise_guide(name) for name in user_data.BASE_EXERCISES]
    return {"guides": guides}


def handle(form):
    day = form.get("day", "").strip()
    if not day:
        return "ไม่พบวันที่ต้องการบันทึก"
    progress = user_data.load("progress", {})
    progress[day] = form.get("done") == "true"
    user_data.save("progress", progress)
    return "บันทึกสถานะการออกกำลังกายแล้ว"
