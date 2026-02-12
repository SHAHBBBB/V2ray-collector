import requests
import re
import base64
import os

CHANNELS = [
    "XIXVPN",
    "persianvpnhub",
]

PROTOCOLS = ["vmess://", "vless://", "trojan://", "ss://", "ssr://", "hysteria2://", "hy2://", "tuic://"]

def fetch_from_telegram(channel):
    configs = []
    try:
        url = f"https://t.me/s/{channel}"
        print(f"Fetching: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200:
            text = r.text

            # مستقیم لینک‌ها داخل HTML
            for protocol in PROTOCOLS:
                pattern = re.escape(protocol) + r'[A-Za-z0-9+/=@:%._~#?&\-]+'
                found = re.findall(pattern, text)
                configs.extend(found)

            # پیدا کردن بلاک‌های base64 و دیکد کردن
            b64_pattern = r'[A-Za-z0-9+/=]{80,}'  # کمی طولانی‌تر تا الکی نخوره
            b64_blocks = re.findall(b64_pattern, text)
            for block in b64_blocks:
                try:
                    decoded = base64.b64decode(block).decode("utf-8", errors="ignore")
                    for line in decoded.splitlines():
                        line = line.strip()
                        if any(line.startswith(p) for p in PROTOCOLS):
                            configs.append(line)
                except Exception:
                    pass

            print(f"  Found {len(configs)} raw configs from @{channel}")
        else:
            print(f"  HTTP {r.status_code} for @{channel}")
    except Exception as e:
        print(f"  Error for @{channel}: {e}")
    return configs

def clean_configs(configs):
    cleaned = []
    seen = set()

    for c in configs:
        c = c.strip()
        if not c:
            continue
        if not any(c.startswith(p) for p in PROTOCOLS):
            continue
        # لینک‌های خیلی کوتاه معمولاً خرابن
        if len(c) < 20:
            continue
        if c in seen:
            continue
        seen.add(c)
        cleaned.append(c)

    return cleaned

def main():
    all_configs = []

    for channel in CHANNELS:
        configs = fetch_from_telegram(channel)
        all_configs.extend(configs)

    all_configs = clean_configs(all_configs)
    print(f"\nTotal unique cleaned configs: {len(all_configs)}")

    os.makedirs("output", exist_ok=True)

    # لیست خام
    with open("output/sub.txt", "w") as f:
        f.write("\n".join(all_configs))

    # نسخه base64 برای بعضی کلاینت‌ها
    encoded = base64.b64encode("\n".join(all_configs).encode()).decode()
    with open("output/base64.txt", "w") as f:
        f.write(encoded)

    print("Done!")

if __name__ == "__main__":
    main()