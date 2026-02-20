#!/usr/bin/env python3
"""
local_scan.py — Run scanner locally on collected configs

Steps:
  1. git pull   — fetch latest configs from GitHub
  2. scanner.py — test latency + speed on YOUR network
  3. output/    — update sub.txt and base64.txt with alive configs sorted by score

Usage:
  python3 local_scan.py                   # default (quick mode)
  python3 local_scan.py --mode normal     # more thorough, slower
  python3 local_scan.py --skip-download   # ping only (fastest)
  python3 local_scan.py --no-pull         # skip git pull
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
    print("[*] Running git pull ...")
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
        "last_scan":       time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scanned_by":      "local",
        "config_count":    len(uris),
        "total_tested":    total_input,
        "elapsed_seconds": round(elapsed, 1),
    }
    with open(OUT_STATS, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] {len(uris)} alive configs saved -> output/sub.txt")
    print(f"[OK] output/base64.txt updated")
    print(f"[OK] output/stats.json updated")


async def run(args):
    # Load
    print(f"\n[*] Loading configs from {INPUT_FILE} ...")
    if not os.path.isfile(INPUT_FILE):
        print(f"[!] File not found: {INPUT_FILE}")
        sys.exit(1)

    st = State()
    st.mode = args.mode
    st.input_file = INPUT_FILE
    if args.skip_download:
        st.rounds = []

    st.configs = load_input(INPUT_FILE)
    total_input = len(st.configs)
    print(f"[*] Loaded {total_input} configs")

    if not st.configs:
        print("[!] No configs found. Exiting.")
        sys.exit(0)

    # DNS
    print(f"[*] Resolving DNS ...")
    await resolve_all(st)
    print(f"[*] {len(st.ips)} unique IPs to test")

    if not st.ips:
        print("[!] No IPs resolved. Exiting.")
        sys.exit(0)

    # Scan
    mode_desc = {
        "quick":    "(~2-3 min)",
        "normal":   "(~5-10 min)",
        "thorough": "(~20-45 min)",
    }
    print(f"[*] Starting scan — mode: {args.mode} {mode_desc.get(args.mode, '')}")
    if args.skip_download:
        print("[*] Ping only — no download speed test")
    print()

    start = time.monotonic()

    scan_task = asyncio.ensure_future(
        run_scan(st, args.workers, args.speed_workers,
                 args.timeout, args.speed_timeout)
    )

    old_sigint = signal.getsignal(signal.SIGINT)

    def _sig(sig, frame):
        st.interrupted = True
        st.finished = True
        scan_task.cancel()
        print("\n\n[!] Interrupted — saving partial results ...")

    signal.signal(signal.SIGINT, _sig)

    async def _progress():
        spin = "|/-\\"
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
                f"{done}/{total} ({pct:>3}%)  alive={alive}   ",
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
    print(f"\n\n[OK] Scan complete — {_fmt(elapsed)} | alive: {st.alive_n}/{len(st.ips)}")

    # Results
    alive_results = sorted_alive(st, "score")

    if not alive_results:
        print("[!] WARNING: No alive configs found. output/sub.txt unchanged.")
        sys.exit(0)

    print(f"\n{'='*72}")
    print(f"  {'#':>3}  {'IP':<16}  {'Ping':>7}  {'Speed':>9}  {'Score':>6}  {'Colo':>4}")
    print(f"  {'─'*3}  {'─'*16}  {'─'*7}  {'─'*9}  {'─'*6}  {'─'*4}")
    for rank, r in enumerate(alive_results[:25], 1):
        lat  = f"{r.tls_ms:>5.0f}ms"      if r.tls_ms   > 0 else "      - "
        spd  = f"{r.best_mbps:>7.2f}MB/s" if r.best_mbps > 0 else "        -"
        sc   = f"{r.score:>6.1f}"         if r.score    > 0 else "     -"
        colo = r.colo or "  -"
        print(f"  {rank:>3}  {r.ip:<16}  {lat}  {spd}  {sc}  {colo:>4}")
    if len(alive_results) > 25:
        print(f"  ... and {len(alive_results)-25} more alive configs")
    print(f"{'='*72}\n")

    # Keep only configs that had a successful speed test
    speed_results = [r for r in alive_results if r.best_mbps > 0]

    if not speed_results:
        print("[!] WARNING: No configs with speed data. output/sub.txt unchanged.")
        sys.exit(0)

    ordered_uris = [uri for r in speed_results for uri in r.uris]

    write_outputs(ordered_uris, elapsed, total_input)

    print(f"\n  Total input      : {total_input} configs")
    print(f"  Alive            : {len(alive_results)} configs")
    print(f"  With speed (kept): {len(ordered_uris)} configs")
    print(f"  Removed          : {total_input - len(ordered_uris)} configs")


def main():
    p = argparse.ArgumentParser(
        description="Scan V2Ray configs locally on your own network"
    )
    p.add_argument("--mode", "-m",
                   choices=["quick", "normal", "thorough"],
                   default="quick",
                   help="Scan mode (default: quick)")
    p.add_argument("--skip-download", action="store_true",
                   help="Ping only — no download speed test")
    p.add_argument("--no-pull", action="store_true",
                   help="Skip git pull")
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
        print("\n[!] Exiting.")


if __name__ == "__main__":
    main()
