import requests
import re
import base64
import os

SOURCES = [
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/normal/mix",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/reality",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/vless",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/vmess",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/trojan",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/shadowsocks",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/hysteria2",
    "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/Sub1.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/Sub2.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/Sub3.txt",
    "https://raw.githubusercontent.com/MhdiTahworworworworworGhworworworworwor free/master/v2ray",
]

PROTOCOLS = ["vmess://", "vless://", "trojan://", "ss://", "ssr://", "hysteria2://", "hy2://"]

def fetch_configs():
    all_configs = []
    for url in SOURCES:
        try:
            print(f"Fetching: {url}")
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                text = r.text
                try:
                    decoded = base64.b64decode(text).decode("utf-8", errors="ignore")
                    text = decoded
                except:
                    pass
                lines = text.splitlines()
                configs = [l.strip() for l in lines if any(l.strip().startswith(p) for p in PROTOCOLS)]
                print(f"  Found {len(configs)} configs")
                all_configs.extend(configs)
            else:
                print(f"  HTTP {r.status_code}")
        except Exception as e:
            print(f"  Error: {e}")
    return all_configs

def main():
    configs = fetch_configs()
    configs = list(set(configs))
    print(f"\nTotal unique configs: {len(configs)}")

    os.makedirs("output", exist_ok=True)

    with open("output/sub.txt", "w") as f:
        f.write("\n".join(configs))

    encoded = base64.b64encode("\n".join(configs).encode()).decode()
    with open("output/base64.txt", "w") as f:
        f.write(encoded)

    print("Done!")

if __name__ == "__main__":
    main()