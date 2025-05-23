#!/usr/bin/env python3
import os
import time
import json
import requests
from datetime import datetime, timezone
from datetime import datetime, timedelta


# Cấu hình Telegram
TELEGRAM_BOT_TOKEN = "7734494245:AAGgkR9F5zt-Ea5UvvYi5qkWnzE_FVSTRlY"
TELEGRAM_CHAT_ID = "5898979798"
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# File log chính (interface up/down)
LOG_FILE = "/var/log/logstash/telegram_debug.log"
OFFSET_FILE = "/home/elk/telegram_debug.offset"

# Cấu hình Elasticsearch
ES_URL = "http://192.168.240.130:9200"
ES_INDEX = "cisco-metrics-*"  
ES_QUERY_INTERVAL_SECONDS = 60  # query dữ liệu 60 giây gần nhất

# Lưu thời điểm lần cuối lấy dữ liệu Elasticsearch
last_es_query_time = None

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

def handle_main_event(event):
    timestamp = event.get("@timestamp", "No timestamp")
    description = event.get("description", "No description provided")
    if isinstance(description, list):
        description = "\n".join(description)

    message_text = (
        "<b>📢 Network Event Alert</b>\n"
        f"<b>Timestamp:</b> {timestamp} UTC\n"
        f"<b>Description:</b> {description}\n\n"
        "<a href='http://192.168.240.130:5601'>🔍 Check Kibana</a>"
    )
    send_telegram_message(message_text)

def query_elasticsearch_alerts():
    global last_es_query_time

    # Lấy thời gian hiện tại UTC
    now = datetime.now(timezone.utc)

    # Nếu chưa có lần query trước, lấy dữ liệu 5 phút trước
    if last_es_query_time is None:
        last_es_query_time = now - timedelta(minutes=5)

    # Khoảng thời gian query
    start_time = last_es_query_time.isoformat() + "Z"
    end_time = now.isoformat() + "Z"

    last_es_query_time = now  # Cập nhật thời gian query mới

    # Query Elasticsearch DSL để lấy các tài liệu có timestamp trong khoảng này
    query = {
        "query": {
            "range": {
                "@timestamp": {
                    "gte": start_time,
                    "lt": end_time
                }
            }
        },
        "size": 100,
        "sort": [{"@timestamp": {"order": "asc"}}]
    }

    try:
        url = f"{ES_URL}/{ES_INDEX}/_search"
        headers = {"Content-Type": "application/json"}
        resp = requests.get(url, headers=headers, json=query, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print("❌ Lỗi khi truy vấn Elasticsearch:", e)
        return []

    hits = data.get("hits", {}).get("hits", [])
    alerts = []
    for hit in hits:
        source = hit.get("_source", {})
        alerts.append(source)
    return alerts

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

def process_elasticsearch_alerts():
    alerts = query_elasticsearch_alerts()
    if not alerts:
        print("Không có cảnh báo mới từ Elasticsearch.")
        return

    for alert in alerts:
        timestamp = alert.get("@timestamp", "No timestamp")
        metric = alert.get("metric_type", "Unknown metric")
        device_ip = alert.get("device_ip", "Unknown device")
        device_model = alert.get("device_model", "Unknown model")
        metric_type = alert.get("metric_type", "Unknown metric")
        value = alert.get("value", "N/A")

      

        message_text = (
            f"<b>⚠️ Alert from Elasticsearch</b>\n"
            f"<b>Timestamp:</b> {timestamp}\n"
            f"<b>Device IP:</b> {device_ip}\n"
            f"<b>Device_name:</b> {device_model}\n"
            f"<b>Metric:</b> {metric_type}\n"
            "<a href='http://192.168.240.130:5601'>🔍 Check Kibana</a>"
        )
        send_telegram_message(message_text)
        time.sleep(1)


if __name__ == "__main__":
    while True:
        process_log_file(LOG_FILE, OFFSET_FILE, handle_main_event)
        process_elasticsearch_alerts()
        time.sleep(30)
