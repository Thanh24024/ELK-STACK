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

last_es_query = None
prev_down = set()  # theo dõi cổng DOWN trước đó

def format_timestamp_vn(iso_ts):
    """Chuyển ISO8601 UTC → giờ VN và định dạng HH:MM:SS."""
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
            print("✅ Tin nhắn đã gửi thành công!")
            return True
    except Exception as e:
        print("❌ Lỗi gửi Telegram:", e)
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
    except:
        return []

def monitor_ports():
    global prev_down
    oper_base  = "iso.org.dod.internet.mgmt.mib-2.interfaces.ifTable.ifEntry.ifOperStatus"
    descr_base = "iso.org.dod.internet.mgmt.mib-2.interfaces.ifTable.ifEntry.ifDescr"

    entries = query_es()
    if not entries:
        return

    # Tập hợp tất cả cổng DOWN trong lô bản ghi
    current_down = set()
    for src in entries:
        for key, val in src.items():
            if key.startswith(oper_base + ".") and int(val) == 2:
                idx = key.split(".")[-1]
                name = src.get(f"{descr_base}.{idx}", f"ifIndex {idx}")
                current_down.add((src.get("device_ip",""), name))

    # Nếu có cổng DOWN mới
    if current_down:
        # chỉ gửi cảnh báo nếu khác với prev_down
        if current_down != prev_down:
            # gom theo thiết bị
            by_dev = {}
            for ip, port in current_down:
                by_dev.setdefault(ip, []).append(port)
            for ip, ports in by_dev.items():
                ts = format_timestamp_vn(entries[-1].get("@timestamp",""))
                model = next((s.get("device_model") for s in entries if s.get("device_ip")==ip), ip)
                ports_list = ", ".join(ports)
                msg = (
                    f"<b>🔴 CẢNH BÁO CỔNG DOWN</b>\n"
                    f"<b>⏱ Thời gian:</b> {ts}\n"
                    f"<b>📡 Thiết bị:</b> {model} ({ip})\n"
                    f"<b>🚨 Cổng DOWN:</b> {ports_list}\n\n"
                    "<a href='http://192.168.240.130:5601'>🔍 Xem trên Kibana</a>"
                )
                send_telegram(msg)
        prev_down = current_down

    # Nếu không còn cổng DOWN nhưng trước đó có
    elif prev_down:
        # gửi tắt cảnh báo
        ts = format_timestamp_vn(entries[-1].get("@timestamp",""))
        msg = (
            f"<b>🟢 TẤT CẢ CỔNG ĐÃ UP</b>\n"
            f"<b>⏱ Thời gian:</b> {ts}\n"
            "<b>📡 Mọi cổng đã hoạt động bình thường.</b>"
        )
        send_telegram(msg)
        prev_down = set()

if __name__ == "__main__":
    while True:
        monitor_ports()
        time.sleep(5)
