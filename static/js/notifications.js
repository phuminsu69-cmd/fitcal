(function () {
  const storageKey = "fitcalc-notifications";
  const defaults = {
    water: { time: "09:00", enabled: true, title: "ถึงเวลาดื่มน้ำ", body: "ดื่มน้ำสักแก้วเพื่อดูแลร่างกายกันนะ" },
    meal: { time: "12:00", enabled: true, title: "เตือนบันทึกมื้ออาหาร", body: "อย่าลืมบันทึกอาหารและแคลอรี่ของมื้อนี้" },
    workout: { time: "18:00", enabled: true, title: "ถึงเวลาออกกำลังกาย", body: "พร้อมขยับร่างกายตามแผน FitCalc แล้วหรือยัง" }
  };
  const settings = Object.assign({}, defaults, JSON.parse(localStorage.getItem(storageKey) || "{}"));
  const button = document.getElementById("notification-enable");
  const status = document.getElementById("notification-status");
  if (!button || !status) return;

  function save() {
    localStorage.setItem(storageKey, JSON.stringify(settings));
  }

  function updateStatus() {
    if (!("Notification" in window)) {
      status.textContent = "เบราว์เซอร์นี้ไม่รองรับ";
    } else if (Notification.permission === "granted") {
      status.textContent = "เปิดใช้งานแล้ว";
    } else if (Notification.permission === "denied") {
      status.textContent = "ถูกบล็อก — อนุญาตจากการตั้งค่าเบราว์เซอร์";
    } else {
      status.textContent = "ยังไม่ได้เปิดใช้งาน";
    }
    button.textContent = Notification.permission === "granted" ? "ทดสอบแจ้งเตือน" : "เปิดการแจ้งเตือน";
  }

  function showInPageNotice(item) {
    let toast = document.getElementById("fitcalc-notification-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "fitcalc-notification-toast";
      toast.className = "fitcalc-notification-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = item.title + " — " + item.body;
    toast.classList.add("visible");
    window.setTimeout(function () { toast.classList.remove("visible"); }, 7000);
  }

  function notify(item) {
    showInPageNotice(item);
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification(item.title, { body: item.body, icon: "/static/eng-logo.png" });
    }
  }

  function checkReminders() {
    const now = new Date();
    const today = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0") + "-" + String(now.getDate()).padStart(2, "0");
    const currentMinutes = now.getHours() * 60 + now.getMinutes();
    Object.keys(settings).forEach(function (key) {
      const item = settings[key];
      const parts = item.time.split(":");
      const reminderMinutes = Number(parts[0]) * 60 + Number(parts[1]);
      const lastKey = today + "-" + reminderMinutes;
      const withinCurrentMinute = currentMinutes === reminderMinutes;
      if (item.enabled && withinCurrentMinute && localStorage.getItem("fitcalc-last-" + key) !== lastKey) {
        notify(item);
        localStorage.setItem("fitcalc-last-" + key, lastKey);
      }
    });
  }

  button.addEventListener("click", function () {
    if (!("Notification" in window)) {
      showInPageNotice({ title: "FitCalc", body: "เบราว์เซอร์นี้ไม่รองรับการแจ้งเตือน" });
      return;
    }
    if (Notification.permission === "granted") {
      notify({ title: "FitCalc เปิดใช้งานแล้ว", body: "ระบบจะแจ้งเตือนตามเวลาที่คุณตั้งไว้" });
      return;
    }
    Notification.requestPermission().then(updateStatus);
  });

  ["water", "meal", "workout"].forEach(function (key) {
    const time = document.getElementById(key + "-reminder");
    const enabled = document.getElementById(key + "-enabled");
    if (!time || !enabled) return;
    time.value = settings[key].time;
    enabled.checked = settings[key].enabled;
    time.addEventListener("change", function () { settings[key].time = time.value; save(); });
    enabled.addEventListener("change", function () { settings[key].enabled = enabled.checked; save(); });
  });

  updateStatus();
  window.addEventListener("focus", checkReminders);
  setInterval(checkReminders, 30000);
  checkReminders();
})();
