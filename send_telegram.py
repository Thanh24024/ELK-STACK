#!/usr/bin/env python3
import requests
import time
import json
import requests

# Thông tin bot Telegram và chat_id
BOT_TOKEN = "7734494245:AAGgkR9F5zt-Ea5UvvYi5qkWnzE_FVSTRlY"
CHAT_ID = "5898979798"

ELK_URL = "http://192.168.240.130:9200/cisco-metrics-*/_search"

# Header JSON cho Elasticsearch
HEADERS = {
    "Content-Type": "application/json"
}

# Lưu cảnh báo đã gửi lần trước để tránh spam
last_alert_message = ""

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload)
        if resp.status_code != 200:
            print(f"Failed to send message: {resp.text}")
    except Exception as e:
        print(f"Exception sending telegram message: {e}")

def query_elk(query):
    try:
        resp = requests.post(ELK_URL, headers=HEADERS, json=query)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error querying ELK: {e}")
        return None

def check_interface_status():
    query = {
        "size": 100,
        "query": {
            "bool": {
                "must": [
                    {"term": {"metric_type": "bandwidth"}},
                    {
                        "terms": {
                            "interface_status_name": ["down", "up"]
                        }
                    }
                ],
                "filter": {
                    "range": {
                        "@timestamp": {
                            "gte": "now-1m"
                        }
                    }
                }
            }
        },
        "sort": [{"@timestamp": {"order": "desc"}}]
    }
    data = query_elk(query)
    alerts = []
    if data and "hits" in data and "hits" in data["hits"]:
        for hit in data["hits"]["hits"]:
            source = hit["_source"]
            status = source.get("interface_status_name", "")
            iface = source.get("interface_name", "unknown")
            device = source.get("device_name", source.get("device_ip", "unknown"))
            if status in ["down", "up"]:
                alerts.append(f"⚠️ Interface *{iface}* on device *{device}* is *{status.upper()}*")
    return alerts

def check_cpu():
    query = {
        "size": 100,
        "query": {
            "bool": {
                "must": [
                    {"term": {"metric_type": "cpu"}},
                    {
                        "range": {
                            "cpu_5m_percent": {
                                "gte": 1
                            }
                        }
                    }
                ],
                "filter": {
                    "range": {
                        "@timestamp": {
                            "gte": "now-1m"
                        }
                    }
                }
            }
        },
        "sort": [{"@timestamp": {"order": "desc"}}]
    }
    data = query_elk(query)
    alerts = []
    if data and "hits" in data and "hits" in data["hits"]:
        for hit in data["hits"]["hits"]:
            src = hit["_source"]
            device = src.get("device_name", src.get("device_ip", "unknown"))
            cpu = src.get("cpu_5m_percent", 0)
            alerts.append(f"🔥 CPU high on *{device}*: {cpu}% (5 min avg)")
    return alerts

def check_ram():
    query = {
        "size": 100,
        "query": {
            "bool": {
                "must": [
                    {"term": {"metric_type": "memory"}},
                    {
                        "range": {
                            "memory_used_percent": {
                                "gte": 1
                            }
                        }
                    }
                ],
                "filter": {
                    "range": {
                        "@timestamp": {
                            "gte": "now-1m"
                        }
                    }
                }
            }
        },
        "sort": [{"@timestamp": {"order": "desc"}}]
    }
    data = query_elk(query)
    alerts = []
    if data and "hits" in data and "hits" in data["hits"]:
        for hit in data["hits"]["hits"]:
            src = hit["_source"]
            device = src.get("device_name", src.get("device_ip", "unknown"))
            ram = src.get("memory_used_percent", 0)
            alerts.append(f"🧠 RAM usage high on *{device}*: {ram}%")
    return alerts

def check_temperature():
    query = {
        "size": 100,
        "query": {
            "bool": {
                "must": [
                    {"term": {"metric_type": "temperature"}},
                    {
                        "range": {
                            "temp_celsius": {
                                "gte": 1
                            }
                        }
                    }
                ],
                "filter": {
                    "range": {
                        "@timestamp": {
                            "gte": "now-1m"
                        }
                    }
                }
            }
        },
        "sort": [{"@timestamp": {"order": "desc"}}]
    }
    data = query_elk(query)
    alerts = []
    if data and "hits" in data and "hits" in data["hits"]:
        for hit in data["hits"]["hits"]:
            src = hit["_source"]
            device = src.get("device_name", src.get("device_ip", "unknown"))
            temp = src.get("temp_celsius", 0)
            alerts.append(f"🌡️ Temperature high on *{device}*: {temp} °C")
    return alerts

def check_bandwidth():
    query = {
        "size": 100,
        "query": {
            "bool": {
                "must": [
                    {"term": {"metric_type": "bandwidth"}},
                    {
                        "range": {
                            "bits_in": {
                                "gte": 100  # > 1 Gbps
                            }
                        }
                    }
                ],
                "filter": {
                    "range": {
                        "@timestamp": {
                            "gte": "now-1m"
                        }
                    }
                }
            }
        },
        "sort": [{"@timestamp": {"order": "desc"}}]
    }
    data = query_elk(query)
    alerts = []
    if data and "hits" in data and "hits" in data["hits"]:
        for hit in data["hits"]["hits"]:
            src = hit["_source"]
            device = src.get("device_name", src.get("device_ip", "unknown"))
            iface = src.get("interface_name", "unknown")
            bits_in = src.get("bits_in", 0)
            bits_out = src.get("bits_out", 0)
            alerts.append(f"📶 Bandwidth high on *{device}* interface *{iface}*: In={bits_in}bps Out={bits_out}bps")
    return alerts

def main_loop():
    global last_alert_message
    while True:
        try:
            alerts = []
            alerts.extend(check_interface_status())
            alerts.extend(check_cpu())
            alerts.extend(check_ram())
            alerts.extend(check_temperature())
            alerts.extend(check_bandwidth())

            if alerts:
                message = "\n\n".join(alerts)
                # So sánh với tin nhắn trước, nếu khác mới gửi
                if message != last_alert_message:
                    send_telegram_message(message)
                    last_alert_message = message
                else:
                    print("Alert unchanged, not sending again.")
            else:
                print("No alerts at this time.")
                last_alert_message = ""
        except Exception as e:
            print(f"Error in main loop: {e}")

        time.sleep(30)

if __name__ == "__main__":
    main_loop()
