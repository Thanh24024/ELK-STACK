#!/usr/bin/env python3
import os
import time
import json
import requests

# Cấu hình Telegram mới
TELEGRAM_BOT_TOKEN = "7734494245:AAGgkR9F5zt-Ea5UvvYi5qkWnzE_FVSTRlY"
TELEGRAM_CHAT_ID = "5898979798"
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# File log theo dõi
LOG_FILE = "/var/log/logstash/telegram_debug.log"
OFFSET_FILE = "/home/elk/telegram_debug.offset"

def get_offset(offset_path, log_path):
    if os.path.exists(offset_path):
        try:
            with open(offset_path, "r") as f:
                return int(f.read().strip())
        except:
            return 0
    else:
        if os.path.exists(log_path):
            size = os.path.getsize(log_path)
            save_offset(offset_path, size)
            return size
        else:
            return 0

def save_offset(offset_path, offset):
    try:
        with open(offset_path, "w") as f:
            f.write(str(offset))
    except Exception as e:
        print("Lỗi khi lưu offset:", e)

def send_telegram_message(text):
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(TELEGRAM_URL, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Tin nhắn đã được gửi thành công!")
            return True
        else:
            print("❌ Lỗi gửi tin nhắn:", response.status_code, response.text)
            return False
    except Exception as e:
        print("❌ Lỗi exception khi gửi:", e)
        return False

def handle_event(event):
    timestamp = event.get("@timestamp", "No timestamp")
    description = event.get("description", "No description")
    alert_type = event.get("alert_type", "Unknown")  # Kiểu cảnh báo: "cpu", "ram", "port", etc.
    severity = event.get("severity", "info")         # Mức độ cảnh báo

    if isinstance(description, list):
        description = "\n".join(description)

    message_text = (
        "<b>🚨 CẢNH BÁO HỆ THỐNG</b>\n"
        f"<b>Loại:</b> {alert_type.upper()}\n"
        f"<b>Mức độ:</b> {severity}\n"
        f"<b>Thời gian:</b> {timestamp} UTC\n"
        f"<b>Chi tiết:</b> {description}\n\n"
        "<a href='http://192.168.240.130:5601'>🔍 Xem trên Kibana</a>"
    )

    send_telegram_message(message_text)

def process_log_file(log_path, offset_path, handler):
    if not os.path.exists(log_path):
        print(f"⛔ File {log_path} không tồn tại.")
        return

    current_offset = get_offset(offset_path, log_path)

    with open(log_path, "r") as f:
        f.seek(current_offset)
        new_lines = f.readlines()
        new_offset = f.tell()

    if not new_lines:
        return

    for line in new_lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            print("⚠️ Không thể parse dòng:", line)
            continue

        handler(event)
        time.sleep(1)

    save_offset(offset_path, new_offset)
    print(f"✔ Đã cập nhật offset: {new_offset}")

if __name__ == "__main__":
    while True:
        process_log_file(LOG_FILE, OFFSET_FILE, handle_event)
        time.sleep(30)
