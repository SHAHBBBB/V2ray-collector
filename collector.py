import requests
import re
import base64
import os
import subprocess
import sys
import html

CHANNELS = [
    "XIXVPN",
    "persianvpnhub",
    "xsfilternet",
    "irdevs_dns",
    "YeBeKhe",
    "cpy_teeL",
    "makvaslim",
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
            
            # Decode HTML entities
            text = html.unescape(text)

            # پیدا کردن کانفیگ‌ها با regex بهبود یافته
            # این pattern تا انتهای line یا تا < و > و space پیش میره
            for protocol in PROTOCOLS:
                # Pattern جدید که کانفیگ‌های کامل رو می‌گیره
                pattern = re.escape(protocol) + r'[^\s<>"\'\n]+'
                found = re.findall(pattern, text)
                
                for config in found:
                    # حذف کاراکترهای اضافی از انتها
                    config = config.rstrip(',;.')
                    configs.append(config)

            # پیدا کردن بلاک‌های base64 و دیکد کردن
            b64_pattern = r'[A-Za-z0-9+/=]{80,}'
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
        
        # حذف HTML entities اگر باقی مونده
        c = html.unescape(c)
        
        if not c:
            continue
        if not any(c.startswith(p) for p in PROTOCOLS):
            continue
        if len(c) < 20:  # لینک‌های خیلی کوتاه معمولاً خرابن
            continue
            
        # بررسی اینکه کانفیگ پارامترهای اساسی داره
        # حداقل باید @ و : داشته باشه
        if '@' not in c or ':' not in c:
            continue
            
        if c in seen:
            continue
        seen.add(c)
        cleaned.append(c)

    return cleaned

def commit_output():
    try:
        # Git config
        subprocess.run(["git", "config", "user.name", "GitHub Actions"], check=True)
        subprocess.run(["git", "config", "user.email", "actions@github.com"], check=True)
        
        # Add files
        subprocess.run(["git", "add", "output/*"], check=True)
        
        # Commit
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
        if result.returncode != 0:
            subprocess.run(["git", "commit", "-m", "Update configs"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("✅ Files committed and pushed successfully!")
        else:
            print("ℹ️ No changes to commit")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git error: {e}")
        sys.exit(1)

def main():
    all_configs = []

    for channel in CHANNELS:
        configs = fetch_from_telegram(channel)
        all_configs.extend(configs)

    all_configs = clean_configs(all_configs)
    print(f"\nTotal unique cleaned configs: {len(all_configs)}")

    os.makedirs("output", exist_ok=True)

    # لیست خام
    with open("output/sub.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(all_configs))

    # نسخه base64
    encoded = base64.b64encode("\n".join(all_configs).encode()).decode()
    with open("output/base64.txt", "w", encoding="utf-8") as f:
        f.write(encoded)

    print("Files created!")
    print(f"✅ sub.txt: {len(all_configs)} configs")

    # Commit و push
    commit_output()

    print("Done! Check your repo for updated files.")

if __name__ == "__main__":
    main()
