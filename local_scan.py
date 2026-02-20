#!/usr/bin/env python3
"""
local_scan.py — اجرای محلی scanner روی کانفیگ‌های جمع‌آوری‌شده

کار این اسکریپت:
  ① git pull   — آخرین کانفیگ‌ها رو از GitHub می‌گیره
  ② scanner.py — تست latency + speed روی شبکه‌ی خودت
  ③ output/    — sub.txt و base64.txt رو با نتایج مرتب‌شده آپدیت می‌کنه

استفاده:
  python3 local_scan.py                   # حالت پیش‌فرض (quick)
  python3 local_scan.py --mode normal     # دقیق‌تر، کندتر
  python3 local_scan.py --skip-download   # فقط پینگ (سریع‌ترین)
  python3 local_scan.py --no-pull         # بدون git pull
"""

import argparse
import asyncio
import base64
import json
import os
import signal
import subprocess
import sys
import time

REPO_ROOT  = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(REPO_ROOT, "output", "sub.txt")
OUT_SUB    = os.path.join(REPO_ROOT, "output", "sub.txt")
OUT_B64    = os.path.join(REPO_ROOT, "output", "base64.txt")
OUT_STATS  = os.path.join(REPO_ROOT, "output", "stats.json")

sys.path.insert(0, REPO_ROOT)
try:
    from scanner import (
        State, load_input, resolve_all, run_scan,
        calc_scores, sorted_alive,
        LATENCY_WORKERS, SPEED_WORKERS,
        LATENCY_TIMEOUT, SPEED_TIMEOUT,
    )
except ImportError as e:
    print(f"[!] Cannot import scanner.py: {e}")
    print(f"[!] Make sure scanner.py is in the same directory.")
    sys.exit(1)


def _fmt(secs: float) -> str:
    m, s = divmod(int(secs), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def git_pull():
    print("[*] git pull ...")
    try:
        result = subprocess.run(
            ["git", "pull", "--rebase"],
            cwd=REPO_ROOT,
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            out = result.stdout.strip()
            print(f"    {out if out else 'Already up to date.'}")
        else:
            print(f"[!] git pull failed:\n{result.stderr.strip()}")
            print("[!] Continuing with local files...")
    except FileNotFoundError:
        print("[!] git not found — skipping pull.")
    except subprocess.TimeoutExpired:
        print("[!] git pull timed out — skipping.")
    except Exception as e:
        print(f"[!] git pull error: {e} — skipping.")


def write_outputs(uris: list, elapsed: float, total_input: int):
    os.makedirs(os.path.dirname(OUT_SUB), exist_ok=True)

    plain   = "\n".join(uris)
    encoded = base64.b64encode(plain.encode("utf-8")).decode("utf-8")

    with open(OUT_SUB, "w", encoding="utf-8") as f:
        f.write(plain + "\n")

    with open(OUT_B64, "w", encoding="utf-8") as f:
        f.write(encoded + "\n")

    stats = {
        "last_scan":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scanned_by":       "local",
        "config_count":     len(uris),
        "total_tested":     total_input,
        "elapsed_seconds":  round(elapsed, 1),
    }
    with open(OUT_STATS, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print(f"\n[✓] {len(uris)} کانفیگ زنده → output/sub.txt")
    print(f"[✓] output/base64.txt")
    print(f"[✓] output/stats.json")


async def run(args):
    # ── بارگذاری ──────────────────────────────────────────────────────────────
    print(f"\n[*] بارگذاری کانفیگ از {INPUT_FILE} ...")
    if not os.path.isfile(INPUT_FILE):
        print(f"[!] فایل پیدا نشد: {INPUT_FILE}")
        sys.exit(1)

    st = State()
    st.mode = args.mode
    st.input_file = INPUT_FILE
    if args.skip_download:
        st.rounds = []

    st.configs = load_input(INPUT_FILE)
    total_input = len(st.configs)
    print(f"[*] {total_input} کانفیگ بارگذاری شد")

    if not st.configs:
        print("[!] هیچ کانفیگی پیدا نشد.")
        sys.exit(0)

    # ── DNS ───────────────────────────────────────────────────────────────────
    print(f"[*] DNS Resolve ...")
    await resolve_all(st)
    print(f"[*] {len(st.ips)} IP یکتا برای تست")

    if not st.ips:
        print("[!] هیچ IP‌ای resolve نشد.")
        sys.exit(0)

    # ── اسکن ─────────────────────────────────────────────────────────────────
    mode_desc = {
        "quick":    "سریع   (~2-3 دقیقه)",
        "normal":   "معمولی (~5-10 دقیقه)",
        "thorough": "کامل   (~20-45 دقیقه)",
    }
    print(f"[*] شروع اسکن — حالت: {args.mode} {mode_desc.get(args.mode, '')}")
    if args.skip_download:
        print("[*] فقط تست پینگ (بدون تست سرعت)")
    print()

    start = time.monotonic()

    scan_task = asyncio.ensure_future(
        run_scan(st, args.workers, args.speed_workers,
                 args.timeout, args.speed_timeout)
    )

    old_sigint = signal.getsignal(signal.SIGINT)
    interrupted = False

    def _sig(sig, frame):
        nonlocal interrupted
        interrupted = True
        st.interrupted = True
        st.finished = True
        scan_task.cancel()
        print("\n\n[!] متوقف شد — ذخیره‌ی نتایج جزئی ...")

    signal.signal(signal.SIGINT, _sig)

    # Progress bar ساده
    async def _progress():
        spin = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        i = 0
        while not st.finished and not st.interrupted:
            phase   = st.phase_label or st.phase or "..."
            done    = st.done_count
            total   = max(1, st.total)
            pct     = done * 100 // total
            alive   = st.alive_n
            elapsed = _fmt(time.monotonic() - start)
            sp = spin[i % len(spin)]
            print(
                f"\r  {sp} [{elapsed}] {phase:<30} "
                f"{done}/{total} ({pct:>3}%)  زنده={alive}   ",
                end="", flush=True
            )
            i += 1
            await asyncio.sleep(0.5)

    prog = asyncio.ensure_future(_progress())

    try:
        await scan_task
    except asyncio.CancelledError:
        st.interrupted = True
        st.finished = True
        calc_scores(st)
    finally:
        prog.cancel()
        try:
            await prog
        except asyncio.CancelledError:
            pass

    signal.signal(signal.SIGINT, old_sigint)
    elapsed = time.monotonic() - start
    print(f"\n\n[✓] اسکن تموم شد — {_fmt(elapsed)} | زنده: {st.alive_n}/{len(st.ips)}")

    # ── جمع‌آوری نتایج ────────────────────────────────────────────────────────
    alive_results = sorted_alive(st, "score")

    if not alive_results:
        print("[!] هیچ کانفیگ زنده‌ای پیدا نشد. فایل‌ها تغییر نمی‌کنند.")
        sys.exit(0)

    # ── نمایش جدول ───────────────────────────────────────────────────────────
    print(f"\n{'═'*72}")
    print(f"  {'#':>3}  {'IP':<16}  {'Ping':>7}  {'Speed':>9}  {'Score':>6}  {'Colo':>4}")
    print(f"  {'─'*3}  {'─'*16}  {'─'*7}  {'─'*9}  {'─'*6}  {'─'*4}")
    for rank, r in enumerate(alive_results[:25], 1):
        lat  = f"{r.tls_ms:>5.0f}ms"  if r.tls_ms   > 0 else "     - "
        spd  = f"{r.best_mbps:>7.2f}MB/s" if r.best_mbps > 0 else "        -"
        sc   = f"{r.score:>6.1f}"     if r.score    > 0 else "     -"
        colo = r.colo or "  -"
        print(f"  {rank:>3}  {r.ip:<16}  {lat}  {spd}  {sc}  {colo:>4}")
    if len(alive_results) > 25:
        print(f"  ... و {len(alive_results)-25} کانفیگ زنده‌ی دیگه")
    print(f"{'═'*72}\n")

    # ── ذخیره ─────────────────────────────────────────────────────────────────
    ordered_uris = [uri for r in alive_results for uri in r.uris]
    write_outputs(ordered_uris, elapsed, total_input)


def main():
    p = argparse.ArgumentParser(
        description="اسکن محلی کانفیگ‌های V2Ray روی شبکه‌ی خودت"
    )
    p.add_argument("--mode", "-m",
                   choices=["quick", "normal", "thorough"],
                   default="quick",
                   help="حالت اسکن (پیش‌فرض: quick)")
    p.add_argument("--skip-download", action="store_true",
                   help="فقط تست پینگ بدون تست سرعت دانلود")
    p.add_argument("--no-pull", action="store_true",
                   help="بدون git pull")
    p.add_argument("--workers",       type=int,   default=LATENCY_WORKERS)
    p.add_argument("--speed-workers", type=int,   default=SPEED_WORKERS)
    p.add_argument("--timeout",       type=float, default=LATENCY_TIMEOUT)
    p.add_argument("--speed-timeout", type=float, default=SPEED_TIMEOUT)
    args = p.parse_args()

    print("=" * 50)
    print("  V2Ray Local Scanner")
    print("=" * 50)

    if not args.no_pull:
        git_pull()

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\n[!] خروج.")


if __name__ == "__main__":
    main()
