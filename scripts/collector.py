import requests
import re
import base64
import json
import os
from datetime import datetime, timezone, timedelta

# لیست کانال‌های تلگرام که کانفیگ V2Ray منتشر می‌کنند
CHANNELS = [
    "v2rayng_config",
    "v2ray_configs_pool",
    "PrivateVPNs",
    "DirectVPN",
    "VlessConfig",
    "free_v2rayyy",
    "v2ray_outlines_reality",
    "OnlineVPNs",
    "ConfigsHUB",
    "v2rayNGn",
]

# پروتکل‌های V2Ray
V2RAY_PROTOCOLS = [
    "vmess://",
    "vless://",
    "trojan://",
    "ss://",
    "ssr://",
    "hysteria://",
    "hysteria2://",
    "hy2://",
    "tuic://",
    "wireguard://",
]


def fetch_telegram_channel(channel_name):
    """گرفتن محتوای کانال تلگرام از طریق وب"""
    url = f"https://t.me/s/{channel_name}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.text
        else:
            print(f"  ❌ خطا در دریافت {channel_name}: {response.status_code}")
            return ""
    except Exception as e:
        print(f"  ❌ خطا در اتصال به {channel_name}: {e}")
        return ""


def is_today_message(html_snippet):
    """بررسی اینکه آیا پیام مربوط به امروز است"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # تلگرام تاریخ رو به فرمت‌های مختلف نشون میده
    if today in html_snippet:
        return True

    # بررسی تاریخ به فرمت‌های دیگه
    now = datetime.now(timezone.utc)
    date_formats = [
        now.strftime("%b %d"),       # Feb 10
        now.strftime("%B %d"),       # February 10
        now.strftime("%d %b"),       # 10 Feb
        now.strftime("%d %B"),       # 10 February
        now.strftime("%d.%m.%Y"),    # 10.02.2026
        now.strftime("%d/%m/%Y"),    # 10/02/2026
    ]
    for fmt in date_formats:
        if fmt in html_snippet:
            return True
    return False


def extract_configs_from_html(html_content):
    """استخراج کانفیگ‌های V2Ray از محتوای HTML"""
    configs = []

    # جدا کردن پیام‌ها
    messages = re.split(
        r'class="tgme_widget_message_wrap', html_content
    )

    for message in messages:
        # بررسی تاریخ پیام
        time_match = re.search(r'datetime="([^"]+)"', message)
        if time_match:
            msg_date = time_match.group(1)[:10]
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if msg_date != today:
                continue
        else:
            # اگه تاریخ پیدا نشد، با روش دیگه چک کن
            if not is_today_message(message):
                continue

        # استخراج کانفیگ‌ها
        for protocol in V2RAY_PROTOCOLS:
            pattern = re.escape(protocol) + r'[A-Za-z0-9+/=_\-@:?&%.#;,\[\]]+'
            found = re.findall(pattern, message)
            configs.extend(found)

    return configs


def decode_and_extract_from_base64(text):
    """اگر محتوا base64 باشه، دیکدش کن و کانفیگ استخراج کن"""
    configs = []
    # پیدا کردن بلوک‌های base64
    base64_pattern = r'[A-Za-z0-9+/=]{50,}'
    matches = re.findall(base64_pattern, text)

    for match in matches:
        try:
            decoded = base64.b64decode(match + "==").decode("utf-8", errors="ignore")
            for protocol in V2RAY_PROTOCOLS:
                if protocol in decoded:
                    pattern = re.escape(protocol) + r'[^\s<>\"\\]+'
                    found = re.findall(pattern, decoded)
                    configs.extend(found)
        except Exception:
            pass
    return configs


def clean_config(config):
    """تمیز کردن کانفیگ از کاراکترهای اضافی"""
    # حذف تگ‌های HTML
    config = re.sub(r'<[^>]+>', '', config)
    # حذف فضای خالی
    config = config.strip()
    return config


def main():
    all_configs = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"📅 تاریخ امروز (UTC): {today}")
    print(f"🔍 شروع جمع‌آوری از {len(CHANNELS)} کانال...\n")

    for channel in CHANNELS:
        print(f"📡 در حال بررسی: @{channel}")
        html = fetch_telegram_channel(channel)
        if not html:
            continue

        # استخراج مستقیم کانفیگ‌ها
        configs = extract_configs_from_html(html)

        # استخراج از base64
        base64_configs = decode_and_extract_from_base64(html)
        configs.extend(base64_configs)

        # تمیز کردن
        configs = [clean_config(c) for c in configs if len(c) > 20]

        print(f"  ✅ {len(configs)} کانفیگ پیدا شد")
        all_configs.extend(configs)

    # حذف تکراری‌ها
    unique_configs = list(dict.fromkeys(all_configs))

    print(f"\n📊 مجموع کانفیگ‌های یکتا: {len(unique_configs)}")

    # ذخیره به صورت متن ساده (هر کانفیگ در یک خط)
    raw_output = "\n".join(unique_configs)

    # ذخیره به صورت base64 (فرمت subscription)
    sub_output = base64.b64encode(raw_output.encode("utf-8")).decode("utf-8")

    # ساخت پوشه output
    os.makedirs("output", exist_ok=True)

    # ذخیره فایل‌ها
    with open("output/configs.txt", "w", encoding="utf-8") as f:
        f.write(raw_output)

    with open("output/sub.txt", "w", encoding="utf-8") as f:
        f.write(sub_output)

    # ذخیره اطلاعات آپدیت
    info = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "total_configs": len(unique_configs),
        "channels_checked": len(CHANNELS),
        "date": today,
    }
    with open("output/info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)

    print(f"\n✅ فایل‌ها با موفقیت ذخیره شدند!")
    print(f"   - output/configs.txt (متن ساده)")
    print(f"   - output/sub.txt (لینک سابسکریپشن base64)")


if __name__ == "__main__":
    main()