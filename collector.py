import requests
import re
import base64
import os
import subprocess
import sys
import html
import datetime

# لیست کانال‌های مورد نظر شما
CHANNELS = [
    "XIXVPN",
    "persianvpnhub",
    "xsfilternet",
    "irdevs_dns",
    "YeBeKhe",
    "cpy_teeL",
    "makvaslim",
    "config_proxy",
    "DuskFall_NFT",
    "iraniroid",
    "VlessConfig",
]

PROTOCOLS = ["vmess://", "vless://", "trojan://", "ss://", "ssr://", "hysteria2://", "hy2://", "tuic://"]

def normalize_config(config):
    """
    کانفیگ را نرمال می‌کند تا تکراری‌های پنهان شناسایی شوند.
    مثلا: vmess را دیکد می‌کند و فقط آدرس و پورت را می‌گیرد.
    یا در vless بخش نام (#name) را حذف می‌کند.
    """
    config = config.strip()
    
    # پردازش ویژه برای Vmess
    if config.startswith("vmess://"):
        try:
            # حذف پیشوند و دیکد کردن
            json_str = base64.b64decode(config[8:]).decode('utf-8')
            
            # یک روش سریع: پیدا کردن مقادیر کلیدی با regex داخل جیسون
            add_match = re.search(r'"add":"(.*?)"', json_str)
            port_match = re.search(r'"port":([^,}]+)', json_str) # ممکن است عدد یا رشته باشد
            id_match = re.search(r'"id":"(.*?)"', json_str)
            
            if add_match and port_match and id_match:
                # ساخت یک کلید یکتا: vmess://IP:PORT:UUID
                return f"vmess://{add_match.group(1)}:{port_match.group(1)}:{id_match.group(1)}"
        except:
            pass
            
    # پردازش برای Vless, Trojan, Hysteria, SS
    elif any(config.startswith(p) for p in ["vless://", "trojan://", "hysteria2://", "hy2://", "tuic://"]):
        try:
            # این پروتکل‌ها فرمت استانداردی دارند:
            # protocol://user@host:port?params#name
            # ما بخش #name (که اسم کانفیگ است و باعث تفاوت می‌شود) را حذف می‌کنیم
            return config.split('#')[0]
        except:
            pass

    return config

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
            text = html.unescape(text)

            # 1. استخراج مستقیم لینک‌ها
            for protocol in PROTOCOLS:
                # Pattern دقیق‌تر برای گرفتن کل کانفیگ
                pattern = re.escape(protocol) + r'[^\s<>"\'\n]+'
                found = re.findall(pattern, text)
                
                for config in found:
                    config = config.rstrip(',;.')
                    configs.append(config)

            # 2. استخراج از بلاک‌های Base64
            b64_pattern = r'[A-Za-z0-9+/=]{80,}'
            b64_blocks = re.findall(b64_pattern, text)
            for block in b64_blocks:
                try:
                    # اضافه کردن padding اگر نبود
                    missing_padding = len(block) % 4
                    if missing_padding:
                        block += '=' * (4 - missing_padding)

                    decoded = base64.b64decode(block).decode("utf-8", errors="ignore")
                    for line in decoded.splitlines():
                        line = line.strip()
                        if any(line.startswith(p) for p in PROTOCOLS):
                            configs.append(line)
                except Exception:
                    pass

            # حذف تکراری‌های داخل خود کانال
            unique_in_channel = list(set(configs))
            print(f"  Found {len(unique_in_channel)} raw configs from @{channel}")
            return unique_in_channel
        else:
            print(f"  HTTP {r.status_code} for @{channel}")
    except Exception as e:
        print(f"  Error for @{channel}: {e}")
    return []

def clean_configs(configs):
    cleaned = []
    seen = set()

    print("\nCleaning and removing duplicates (Deep Scan)...")

    for c in configs:
        c = c.strip()
        c = html.unescape(c)
        
        if not c:
            continue
        if not any(c.startswith(p) for p in PROTOCOLS):
            continue
        if len(c) < 20:
            continue
            
        # بررسی حداقل ساختار (وجود @ و :)
        if '@' not in c or ':' not in c:
            continue
            
        # === مرحله مهم: نرمال‌سازی برای تشخیص تکراری ===
        norm_c = normalize_config(c)
        
        # اگر نسخه نرمال شده قبلاً دیده شده، پس این کانفیگ تکراری است
        if norm_c in seen:
            continue
            
        seen.add(norm_c)
        cleaned.append(c)

    return cleaned

def commit_output():
    try:
        subprocess.run(["git", "config", "user.name", "GitHub Actions"], check=True)
        subprocess.run(["git", "config", "user.email", "actions@github.com"], check=True)
        subprocess.run(["git", "add", "output/*"], check=True)
        
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if result.stdout.strip():
            subprocess.run(["git", "commit", "-m", f"Update configs - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("✅ Files committed and pushed successfully!")
        else:
            print("ℹ️ No changes to commit")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git error: {e}")
        sys.exit(1)

def main():
    print(f"--- Collector Started at {datetime.datetime.now()} ---")
    all_configs = []

    for channel in CHANNELS:
        configs = fetch_from_telegram(channel)
        all_configs.extend(configs)

    all_configs = clean_configs(all_configs)
    print(f"\nTotal unique cleaned configs: {len(all_configs)}")

    os.makedirs("output", exist_ok=True)

    with open("output/sub.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(all_configs))

    encoded = base64.b64encode("\n".join(all_configs).encode()).decode()
    with open("output/base64.txt", "w", encoding="utf-8") as f:
        f.write(encoded)

    print("Files created!")
    print(f"✅ sub.txt: {len(all_configs)} configs")

    commit_output()

    print("Done! Check your repo for updated files.")

if __name__ == "__main__":
    main()
```
