#!/usr/bin/env python3
import requests
import time
import json
import requests


BOT_TOKEN = "7734494245:AAGgkR9F5zt-Ea5UvvYi5qkWnzE_FVSTRlY"
CHAT_ID = "5898979798"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send_telegram_message(message: str):
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(TELEGRAM_API_URL, data=payload)
        if response.status_code == 200:
            print("Đã gửi cảnh báo Telegram thành công!")
        else:
            print(f"Lỗi khi gửi tin nhắn Telegram: {response.text}")
    except Exception as e:
        print(f"Exception khi gửi Telegram: {e}")

def alert_port_status(device_name, interface_name, status):
    message = (f"⚠️ *Cảnh báo cổng mạng*\n"
               f"Thiết bị: *{device_name}*\n"
               f"Cổng: `{interface_name}` vừa *{status}*.")
    send_telegram_message(message)

def alert_cpu_usage(device_name, cpu_percent, threshold=10.0):
    if cpu_percent >= threshold:
        message = (f"🔥 *Cảnh báo CPU cao*\n"
                   f"Thiết bị: *{device_name}*\n"
                   f"CPU sử dụng: *{cpu_percent}%* (ngưỡng: {threshold}%)")
        send_telegram_message(message)

def alert_memory_usage(device_name, memory_percent, threshold=10.0):
    if memory_percent >= threshold:
        message = (f"🔥 *Cảnh báo RAM cao*\n"
                   f"Thiết bị: *{device_name}*\n"
                   f"RAM sử dụng: *{memory_percent}%* (ngưỡng: {threshold}%)")
        send_telegram_message(message)

def alert_temperature(device_name, temp_celsius, threshold=10.0):
    if temp_celsius >= threshold:
        message = (f"🌡️ *Cảnh báo nhiệt độ cao*\n"
                   f"Thiết bị: *{device_name}*\n"
                   f"Nhiệt độ: *{temp_celsius}°C* (ngưỡng: {threshold}°C)")
        send_telegram_message(message)

def alert_bandwidth(device_name, interface_name, bits_in, bits_out, threshold_bits=10.0):
    # threshold_bits ~ 800Mbps
    if bits_in >= threshold_bits or bits_out >= threshold_bits:
        message = (f"📶 *Cảnh báo băng thông cao*\n"
                   f"Thiết bị: *{device_name}*\n"
                   f"Cổng: `{interface_name}`\n"
                   f"Lưu lượng vào: *{bits_in/1_000_000:.2f} Mbps*\n"
                   f"Lưu lượng ra: *{bits_out/1_000_000:.2f} Mbps*\n"
                   f"Ngưỡng: {threshold_bits/1_000_000} Mbps")
        send_telegram_message(message)



# Ví dụ giả lập gọi hàm (thay thế bằng dữ liệu thực tế khi tích hợp)
if __name__ == "__main__":
    # Ví dụ cổng vừa xuống (down)
    alert_port_status("Switch L3-1", "GigabitEthernet0/1", "xuống")

    # CPU vượt ngưỡng
    alert_cpu_usage("Cisco C7200", 90.5)

    # RAM vượt ngưỡng
    alert_memory_usage("Switch L3-2", 85.3)

    # Nhiệt độ vượt ngưỡng
    alert_temperature("Cisco C7200", 75)

    # Băng thông cao
    alert_bandwidth("Switch L3-1", "GigabitEthernet0/2", 850_000_000, 400_000_000)
