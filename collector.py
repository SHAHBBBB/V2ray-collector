import requests
import re
import base64
import os
import subprocess
import sys
import html
import datetime

CHANNELS = [
    "ShadowProxy66",
    "xsfilternet",
]

PROTOCOLS = ["vmess://", "vless://", "trojan://", "ss://", "ssr://", "hysteria2://", "hy2://", "tuic://"]

def normalize_config(config):
    config = config.strip()
    
    if config.startswith("vmess://"):
        try:
            json_str = base64.b64decode(config[8:]).decode('utf-8')
            add_match = re.search(r'"add":"(.*?)"', json_str)
            port_match = re.search(r'"port":([^,}]+)', json_str)
            id_match = re.search(r'"id":"(.*?)"', json_str)
            
            if add_match and port_match and id_match:
                return f"vmess://{add_match.group(1)}:{port_match.group(1)}:{id_match.group(1)}"
        except:
            pass
            
    elif any(config.startswith(p) for p in ["vless://", "trojan://", "hysteria2://", "hy2://", "tuic://"]):
        try:
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

            for protocol in PROTOCOLS:
                pattern = re.escape(protocol) + r'[^\s<>"\'\n]+'
                found = re.findall(pattern, text)
                
                for config in found:
                    config = config.rstrip(',;.')
                    configs.append(config)

            b64_pattern = r'[A-Za-z0-9+/=]{80,}'
            b64_blocks = re.findall(b64_pattern, text)
            for block in b64_blocks:
                try:
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

            unique_in_channel = list(set(configs))
            print(f"  Found {len(unique_in_channel)} raw configs from @{channel}")
            return unique_in_channel
        else:
            print(f"  HTTP {r.status_code} for @{channel}")
    except Exception as e:
        print(f"  Error for @{channel}: {e}")
    return []

def fetch_from_custom_subs():
    """خواندن لینک‌های سابسکریپشن دستی از فایل custom_subs.txt و استخراج کانفیگ‌ها"""
    configs = []
    subs_file = 'custom_subs.txt'
    if not os.path.exists(subs_file):
        return configs

    with open(subs_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"\nFetching from {len(urls)} custom subscription URLs...")
    for url in urls:
        try:
            print(f"  Fetching: {url}")
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                print(f"    HTTP {r.status_code}")
                continue

            content = r.text.strip()
            if not content:
                continue

            # تلاش برای دیکد base64 (اگر کل محتوا base64 باشد)
            try:
                decoded = base64.b64decode(content).decode('utf-8')
                lines = decoded.splitlines()
            except:
                # اگر دیکد نشد، محتوا را خط به خط به عنوان متن ساده در نظر بگیر
                lines = content.splitlines()

            for line in lines:
                line = line.strip()
                if any(line.startswith(p) for p in PROTOCOLS):
                    configs.append(line)

        except Exception as e:
            print(f"    Error: {e}")

    print(f"  Total raw configs from custom subs: {len(configs)}")
    return configs

def read_configs_from_folder(folder_path='configs'):
    """خواندن تمام فایل‌های داخل پوشه configs و استخراج کانفیگ‌ها"""
    configs = []
    if not os.path.exists(folder_path):
        print(f"Folder {folder_path} not found. Skipping.")
        return configs

    print(f"\nReading configs from folder '{folder_path}'...")
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                file_configs = []
                for line in lines:
                    line = line.strip()
                    if line and any(line.startswith(p) for p in PROTOCOLS):
                        file_configs.append(line)
                configs.extend(file_configs)
                print(f"  Loaded {len(file_configs)} configs from {file_path}")
            except Exception as e:
                print(f"  Error reading {file_path}: {e}")

    print(f"  Total raw configs from folder: {len(configs)}")
    return configs

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
            
        if '@' not in c or ':' not in c:
            continue
            
        norm_c = normalize_config(c)
        
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
            commit_msg = f"Update configs - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(["git", "push"], check=True)
            print("Files committed and pushed successfully!")
        else:
            print("No changes to commit")
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")
        sys.exit(1)

def main():
    print(f"--- Collector Started at {datetime.datetime.now()} ---")
    all_configs = []

    # دریافت از کانال‌های تلگرام
    for channel in CHANNELS:
        configs = fetch_from_telegram(channel)
        all_configs.extend(configs)

    # دریافت از لینک‌های سابسکریپشن دستی
    custom_configs = fetch_from_custom_subs()
    all_configs.extend(custom_configs)

    # دریافت از پوشه configs
    folder_configs = read_configs_from_folder('configs')
    all_configs.extend(folder_configs)

    all_configs = clean_configs(all_configs)
    print(f"\nTotal unique cleaned configs: {len(all_configs)}")

    os.makedirs("output", exist_ok=True)

    with open("output/sub.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(all_configs))

    encoded = base64.b64encode("\n".join(all_configs).encode()).decode()
    with open("output/base64.txt", "w", encoding="utf-8") as f:
        f.write(encoded)

    print("Files created!")
    print(f"sub.txt: {len(all_configs)} configs")

    commit_output()

    print("Done! Check your repo for updated files.")

if __name__ == "__main__":
    main()