#!/usr/bin/env python3
import requests
import json
import time
import warnings
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ElasticsearchWarning

# Tắt cảnh báo bảo mật nếu không dùng
warnings.filterwarnings("ignore", category=ElasticsearchWarning)

# Cấu hình Telegram
TELEGRAM_TOKEN = "7734494245:AAGgkR9F5zt-Ea5UvvYi5qkWnzE_FVSTRlY"
CHAT_ID = "5898979798"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Cấu hình Elasticsearch
ES_HOST = "http://192.168.240.130:9200"
ES_INDEX = "cisco-metrics-*"
ES = Elasticsearch([ES_HOST])  # Thêm auth nếu cần

# Ngưỡng cảnh báo
THRESHOLDS = {
    "cpu": 5,         # % CPU
    "memory": 5,      # % RAM
    "temp": 6,        # °C
    "status_change": True
}

interface_status_cache = {}

def send_telegram_alert(message):
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(TELEGRAM_API_URL, json=payload)
        response.raise_for_status()
        print(f"Đã gửi cảnh báo: {message}")
    except Exception as e:
        print(f"Lỗi khi gửi Telegram: {e}")

def check_alerts():
    time_range = {"gte": "now-15s", "lte": "now"}
    
    try:
        response = ES.search(
            index=ES_INDEX,
            query={
                "bool": {
                    "must": [
                        {"range": {"@timestamp": time_range}},
                        {"exists": {"field": "metric_type"}}
                    ]
                }
            },
            size=100,
            sort=[{"@timestamp": "desc"}]
        )
        
        hits = response.get('hits', {}).get('hits', [])
        
        for hit in hits:
            source = hit.get('_source', {})
            metric_type = source.get('metric_type')
            device_ip = source.get('device_ip', 'Unknown')
            device_name = source.get('device_name', device_ip)
            
            if metric_type == "cpu":
                cpu = source.get('cpu_5m_percent')
                if cpu and cpu > THRESHOLDS['cpu']:
                    message = f"⚠️ <b>CPU CAO</b> ⚠️\nThiết bị: {device_name} ({device_ip})\nCPU 5 phút: <b>{cpu}%</b>\nThời điểm: {source.get('@timestamp')}"
                    send_telegram_alert(message)
            
            elif metric_type == "memory":
                mem = source.get('memory_used_percent')
                if mem and mem > THRESHOLDS['memory']:
                    message = f"⚠️ <b>RAM CAO</b> ⚠️\nThiết bị: {device_name} ({device_ip})\nRAM sử dụng: <b>{mem}%</b>\nTổng RAM: {source.get('memory_total_mb', 'N/A')} MB\nThời điểm: {source.get('@timestamp')}"
                    send_telegram_alert(message)
            
            elif metric_type == "temperature":
                temp = source.get('temp_celsius')
                if temp and temp > THRESHOLDS['temp']:
                    message = f"⚠️ <b>NHIỆT ĐỘ CAO</b> ⚠️\nThiết bị: {device_name} ({device_ip})\nNhiệt độ: <b>{temp}°C</b>\nThời điểm: {source.get('@timestamp')}"
                    send_telegram_alert(message)
            
            elif metric_type == "bandwidth" and THRESHOLDS['status_change']:
                interface = source.get('interface_name')
                current_status = source.get('interface_status_name')
                interface_key = f"{device_ip}_{interface}"
                
                if interface_key in interface_status_cache:
                    previous_status = interface_status_cache[interface_key]
                    if previous_status != current_status:
                        message = f"🔄 <b>THAY ĐỔI TRẠNG THÁI CỔNG</b> 🔄\nThiết bị: {device_name} ({device_ip})\nCổng: <b>{interface}</b>\nTrạng thái: {previous_status} → <b>{current_status}</b>\nThời điểm: {source.get('@timestamp')}"
                        send_telegram_alert(message)
                
                interface_status_cache[interface_key] = current_status
    
    except Exception as e:
        print(f"Lỗi khi query Elasticsearch: {e}")

if __name__ == "__main__":
    print("Bắt đầu giám sát cảnh báo...")
    while True:
        check_alerts()
        time.sleep(15)
