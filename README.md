# V2ray Collector 🔄

[![Last Update](https://img.shields.io/github/last-commit/SHAHBBBB/V2ray-collector?label=Last%20Update)](https://github.com/SHAHBBBB/V2ray-collector/commits/main)
[![Config Count](https://img.shields.io/badge/dynamic/json?label=Configs&query=config_count&url=https://raw.githubusercontent.com/SHAHBBBB/V2ray-collector/main/output/stats.json)](https://github.com/SHAHBBBB/V2ray-collector/blob/main/output/sub.txt)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

این پروژه به صورت خودکار کانفیگ‌های پروکسی (V2Ray) را از کانال‌های تلگرام جمع‌آوری کرده و به‌صورت مرتب به‌روزرسانی می‌کند. خروجی نقی و بدون تکرار در دو قالب `sub.txt` (متن ساده) و `base64.txt` (کدگذاری‌شده) ارائه می‌شود.

## 📥 لینک‌های اشتراک (Subscription)

برای استفاده در کلاینت‌های V2Ray، یکی از لینک‌های زیر را کپی کنید:

| فرمت | لینک |
|------|------|
| متن ساده | [`sub.txt`](https://raw.githubusercontent.com/SHAHBBBB/V2ray-collector/main/output/sub.txt) |
| Base64 | [`base64.txt`](https://raw.githubusercontent.com/SHAHBBBB/V2ray-collector/main/output/base64.txt) |

> نکته: لینک‌ها هر ۳ ساعت یکبار به‌روزرسانی می‌شوند.

## 🌐 منابع جمع‌آوری‌شده (کانال‌های تلگرام)

- [XIXVPN](https://t.me/XIXVPN)
- [persianvpnhub](https://t.me/persianvpnhub)
- [xsfilternet](https://t.me/xsfilternet)
- [irdevs_dns](https://t.me/irdevs_dns)
- [YeBeKhe](https://t.me/YeBeKhe)
- [cpy_teeL](https://t.me/cpy_teeL)
- [makvaslim](https://t.me/makvaslim)
- [config_proxy](https://t.me/config_proxy)
- [DuskFall_NFT](https://t.me/DuskFall_NFT)
- [iraniroid](https://t.me/iraniroid)
- [VlessConfig](https://t.me/VlessConfig)
- [ShadowProxy66](https://t.me/ShadowProxy66)

## ⚙️ نحوه کار

پروژه با استفاده از **GitHub Actions** هر ۳ ساعت یکبار اجرا می‌شود و:
1. از کانال‌های بالا کانفیگ‌ها را استخراج می‌کند.
2. از لینک‌های اشتراک دستی (در صورت وجود) نیز کانفیگ می‌گیرد.
3. کانفیگ‌ها را پالایش و تکراری‌ها را حذف می‌کند.
4. فایل‌های خروجی را در پوشه `output/` به‌روزرسانی و در مخزن کامیت می‌کند.

## 🧪 اجرای شخصی (Self-host)

اگر می‌خواهید این پروژه را روی سرور خودتان اجرا کنید:

```bash
git clone https://github.com/SHAHBBBB/V2ray-collector.git
cd V2ray-collector
pip install requests
python collector.py
