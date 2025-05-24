#!/usr/bin/env python3
import time
import requests
from datetime import datetime, timezone, timedelta

# --- Cấu hình Telegram ---
TELEGRAM_BOT_TOKEN = "7734494245:AAGgkR9F5zt-Ea5UvvYi5qkWnzE_FVSTRlY"
TELEGRAM_CHAT_ID   = "5898979798"
TELEGRAM_URL       = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# --- Elasticsearch ---
ES_URL   = "http://192.168.240.130:9200"
ES_INDEX = "cisco-metrics-*"

# OID textual base
OPER_BASE  = "iso.org.dod.internet.mgmt.mib-2.interfaces.ifTable.ifEntry.ifOperStatus"
DESCR_BASE = "iso.org.dod.internet.mgmt.mib-2.interfaces.ifTable.ifEntry.ifDescr"
CPU_OID    = "iso.org.dod.internet.private.enterprises.9.2.1.58.0"
RAM_OID    = "iso.org.dod.internet.private.enterprises.9.2.1.57.0"
CPU_OID_5s = "1.3.6.1.4.1.9.9.109.1.1.1.1.5"
CPU_OID_1m = "1.3.6.1.4.1.9.9.109.1.1.1.1.6"
CPU_OID_5m = "1.3.6.1.4.1.9.9.109.1.1.1.1.7"

# Lưu thiết bị và thời điểm lần cuối hoạt động
active_devices = {}
alerted_down_devices = set()
alerted_down_devices_auto = set()

last_es_query = None

def format_timestamp_vn(iso_ts):
    try:
        dt = datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%S.%fZ")
        dt_vn = dt + timedelta(hours=7)
        return dt_vn.strftime("%H:%M:%S")
    except:
        return iso_ts

def send_telegram(text):
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(TELEGRAM_URL, json=payload, timeout=10)
        if r.status_code == 200:
            print("📨 Đã gửi cảnh báo Telegram.")
            return True
        else:
            print("⚠️ Lỗi gửi Telegram:", r.text)
            return False
    except Exception as e:
        print("⚠️ Exception khi gửi Telegram:", e)
        return False

def query_es():
    global last_es_query
    now = datetime.now(timezone.utc)
    if last_es_query is None:
        start = (now - timedelta(minutes=5)).isoformat()
    else:
        start = last_es_query.isoformat()
    end = now.isoformat()
    last_es_query = now

    q = {
        "query": {
            "range": {
                "@timestamp": {"gte": start, "lt": end}
            }
        },
        "size": 100,
        "sort": [{"@timestamp": {"order": "asc"}}]
    }
    try:
        resp = requests.get(f"{ES_URL}/{ES_INDEX}/_search", json=q, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        return [h["_source"] for h in hits]
    except Exception as e:
        print("❌ Lỗi truy vấn Elasticsearch:", e)
        return []

def monitor_ports_and_resources():
    entries = query_es()
    if not entries:
        return

    for src in entries:
        ts_iso = src.get("@timestamp", "")
        ts = format_timestamp_vn(ts_iso)
        ip    = src.get("device_ip", "Unknown IP")
        model = src.get("device_model", "Unknown device")
        device_id = f"{model}_{ip}"
        device_key = f"{model}||{ip}"
        active_devices[device_key] = datetime.now()

        # -- Cảnh báo cổng DOWN --
        down_ports = []
        for key, val in src.items():
            if key.startswith(OPER_BASE + ".") and int(val) == 2:
                idx = key.split(".")[-1]
                name = src.get(f"{DESCR_BASE}.{idx}", f"ifIndex {idx}")
                down_ports.append(name)

        if down_ports:
            ports = ", ".join(down_ports)
            msg = (
                f"<b>🔴 CẢNH BÁO CỔNG DOWN</b>\n"
                f"<b>⏱ Thời gian:</b> {ts}\n"
                f"<b>📡 Thiết bị:</b> {model} ({ip})\n"
                f"<b>🚨 Cổng DOWN:</b> {ports}\n\n"
                "<a href='http://192.168.240.130:5601/app/dashboards#/view/8368e280-28eb-11f0-986a-ff8851b2a330?_g=(filters:!(),refreshInterval:(pause:!t,value:0),time:(from:now-15m,to:now))'>🔍 Xem chi tiết trên Kibana</a>"
            )
            send_telegram(msg)

        # -- Cảnh báo CPU & RAM --
        try:
            cpu_5s = float(src.get(CPU_OID_5s, 0))
            cpu_1m = float(src.get(CPU_OID_1m, 0))
            cpu_5m = float(src.get(CPU_OID_5m, 0))
            # Ví dụ dùng CPU 5 phút để cảnh báo
            cpu = cpu_5m  
            ram = float(src.get(RAM_OID, 0))
        except Exception:
            cpu = 0
            ram = 0

        # Cảnh báo CPU nếu vượt 5%
        if cpu > 5:
            msg = (
                f"<b>🔥 CẢNH BÁO CPU CAO</b>\n"
                f"<b>⏱ Thời gian:</b> {ts}\n"
                f"<b>📡 Thiết bị:</b> {model} ({ip})\n"
                f"<b>⚠️ CPU:</b> {cpu:.2f}%\n\n"
                "<a href='http://192.168.240.130:5601'>🔍 Xem chi tiết trên Kibana</a>"
            )
            if send_telegram(msg):
                print(f"[{ts}] Đã gửi cảnh báo CPU thiết bị {model} ({ip}): {cpu:.2f}%")

        # Cảnh báo RAM nếu vượt 5%
        if ram > 5:
            msg = (
                f"<b>📈 CẢNH BÁO RAM CAO</b>\n"
                f"<b>⏱ Thời gian:</b> {ts}\n"
                f"<b>📡 Thiết bị:</b> {model} ({ip})\n"
                f"<b>⚠️ RAM:</b> {ram:.2f}%\n\n"
                "<a href='http://192.168.240.130:5601'>🔍 Xem chi tiết trên Kibana</a>"
            )
            if send_telegram(msg):
                print(f"[{ts}] Đã gửi cảnh báo RAM thiết bị {model} ({ip}): {ram:.2f}%")
            
def check_device_status():
    now = datetime.now()
    for device_key, last_seen in list(active_devices.items()):
        offline_seconds = (now - last_seen).total_seconds()

        if offline_seconds > 30:
            # Gửi cảnh báo offline lần đầu
            if device_key not in alerted_down_devices:
                model, ip = device_key.split("||")
                msg = (
                    f"<b>🔌 THIẾT BỊ MẤT KẾT NỐI</b>\n"
                    f"<b>📡 Thiết bị:</b> {model} ({ip})\n"
                    f"<b>⏱ Thời gian:</b> {now.strftime('%H:%M:%S')}\n\n"
                    "<a href='http://192.168.240.130:5601'>🔍 Xem chi tiết trên Kibana</a>"
                )
                if send_telegram(msg):
                    alerted_down_devices.add(device_key)

            # Gửi cảnh báo nhắc nhở nếu offline thêm 15s mà chưa gửi
            if offline_seconds > 105 and device_key not in alerted_down_devices_auto:
                model, ip = device_key.split("||")
                msg = (
                    f"⚠️ <b>NHẮC NHỞ THIẾT BỊ VẪN OFFLINE</b>\n"
                    f"<b>📡 Thiết bị:</b> {model} ({ip})\n"
                    f"<b>⏱ Offline từ lúc:</b> {(now - timedelta(seconds=offline_seconds)).strftime('%H:%M:%S')}\n"
                    f"<b>⏳ Đã offline:</b> {int(offline_seconds)} giây\n\n"
                    "<a href='http://192.168.240.130:5601'>🔍 Xem chi tiết trên Kibana</a>"
                )
                if send_telegram(msg):
                    alerted_down_devices_auto.add(device_key)

        else:
            # Thiết bị đã lên lại, xóa cảnh báo offline và nhắc nhở
            if device_key in alerted_down_devices:
                model, ip = device_key.split("||")
                msg = f"✅ <b>Thiết bị đã hoạt động lại:</b> {model} ({ip})"
                if send_telegram(msg):
                    alerted_down_devices.remove(device_key)
            if device_key in alerted_down_devices_auto:
                alerted_down_devices_auto.remove(device_key)
if __name__ == "__main__":
    while True:
        monitor_ports_and_resources()
        check_device_status()
        time.sleep(20)
