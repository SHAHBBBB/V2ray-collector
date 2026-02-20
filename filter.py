#!/usr/bin/env python3
"""
filter.py — Integration bridge between V2ray-collector and CF Config Scanner

Flow:
  1. Read collected configs from output/sub.txt
  2. Run latency + speed tests (headless, no TUI)
  3. Sort all alive configs by score (latency 35% + speed 50% + TTFB 15%)
  4. Overwrite output/sub.txt and output/base64.txt with scored+sorted results
  5. Write output/stats.json with scan summary

Usage:
  python3 filter.py                        # default: quick mode
  python3 filter.py --mode normal          # normal mode (more thorough)
  python3 filter.py --mode thorough        # deep test (slow, ~30-45 min)
  python3 filter.py --skip-download        # latency only (fastest)
  python3 filter.py --input custom.txt     # custom input file
"""

import asyncio
import base64
import json
import os
import signal
import sys
import time
import argparse

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT   = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE  = os.path.join(REPO_ROOT, "output", "sub.txt")
OUT_SUB     = os.path.join(REPO_ROOT, "output", "sub.txt")
OUT_B64     = os.path.join(REPO_ROOT, "output", "base64.txt")
OUT_STATS   = os.path.join(REPO_ROOT, "output", "stats.json")
RESULTS_DIR = os.path.join(REPO_ROOT, "results")

# ── Import scanner internals ────────────────────────────────────────────────────
# scanner.py must be in the same directory as filter.py
sys.path.insert(0, REPO_ROOT)
try:
    from scanner import (
        State,
        load_input,
        resolve_all,
        run_scan,
        calc_scores,
        sorted_alive,
        LATENCY_WORKERS,
        SPEED_WORKERS,
        LATENCY_TIMEOUT,
        SPEED_TIMEOUT,
    )
except ImportError as e:
    print(f"[filter] ERROR: Cannot import scanner.py — {e}")
    print(f"[filter] Make sure scanner.py is in the same directory as filter.py")
    sys.exit(1)


def _fmt_elapsed(secs: float) -> str:
    m, s = divmod(int(secs), 60)
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def write_outputs(configs_sorted: list, elapsed: float, total_input: int):
    """Write sub.txt, base64.txt and stats.json."""
    os.makedirs(os.path.dirname(OUT_SUB), exist_ok=True)

    lines = []
    for uri in configs_sorted:
        lines.append(uri)

    plain = "\n".join(lines)
    encoded = base64.b64encode(plain.encode("utf-8")).decode("utf-8")

    with open(OUT_SUB, "w", encoding="utf-8") as f:
        f.write(plain + "\n")

    with open(OUT_B64, "w", encoding="utf-8") as f:
        f.write(encoded + "\n")

    stats = {
        "last_scan": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config_count": len(lines),
        "total_tested": total_input,
        "elapsed_seconds": round(elapsed, 1),
    }
    with open(OUT_STATS, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print(f"[filter] Wrote {len(lines)} configs → output/sub.txt + base64.txt")
    print(f"[filter] Stats → output/stats.json")


async def run_filter(args):
    input_path = getattr(args, "input", None) or INPUT_FILE

    if not os.path.isfile(input_path):
        print(f"[filter] ERROR: Input file not found: {input_path}")
        sys.exit(1)

    # ── Load ──────────────────────────────────────────────────────────────────
    print(f"[filter] Loading configs from {input_path} ...")
    st = State()
    st.mode = args.mode
    st.input_file = input_path

    if args.skip_download:
        st.rounds = []

    st.configs = load_input(input_path)
    total_input = len(st.configs)
    print(f"[filter] Loaded {total_input} configs")

    if not st.configs:
        print("[filter] No configs found. Exiting.")
        sys.exit(0)

    # ── DNS resolve ───────────────────────────────────────────────────────────
    print(f"[filter] Resolving DNS ...")
    await resolve_all(st)
    print(f"[filter] {len(st.ips)} unique IPs to test")

    if not st.ips:
        print("[filter] No IPs resolved. Exiting.")
        sys.exit(0)

    # ── Scan ──────────────────────────────────────────────────────────────────
    print(f"[filter] Starting scan (mode={args.mode}) ...")
    start = time.monotonic()

    scan_task = asyncio.ensure_future(
        run_scan(st, args.workers, args.speed_workers, args.timeout, args.speed_timeout)
    )

    old_sigint = signal.getsignal(signal.SIGINT)
    def _sig(sig, frame):
        st.interrupted = True
        st.finished = True
        scan_task.cancel()
        print("\n[filter] Interrupted — saving partial results ...")
    signal.signal(signal.SIGINT, _sig)

    # Progress reporter
    async def _progress():
        while not st.finished and not st.interrupted:
            phase = st.phase_label or st.phase
            done  = st.done_count
            total = max(1, st.total)
            pct   = done * 100 // total
            alive = st.alive_n
            elapsed = _fmt_elapsed(time.monotonic() - start) if start else "0s"
            print(f"\r[filter] [{elapsed}] {phase} — {done}/{total} ({pct}%) alive={alive}  ", end="", flush=True)
            await asyncio.sleep(2)

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
    print(f"\n[filter] Scan done in {_fmt_elapsed(elapsed)}. Alive: {st.alive_n}/{len(st.ips)}")

    # ── Sort & collect URIs ───────────────────────────────────────────────────
    alive_results = sorted_alive(st, "score")

    if not alive_results:
        print("[filter] WARNING: No alive configs found. Keeping original sub.txt unchanged.")
        sys.exit(0)

    # Collect all URIs, ordered by IP score (best first)
    ordered_uris = []
    for r in alive_results:
        for uri in r.uris:
            ordered_uris.append(uri)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'=' * 75}")
    print(f"{'#':>4}  {'IP':<16}  {'Latency':>8}  {'Speed MB/s':>10}  {'Score':>6}  {'Colo':>5}")
    print(f"{'─' * 75}")
    for rank, r in enumerate(alive_results[:20], 1):
        lat  = f"{r.tls_ms:>7.0f}ms" if r.tls_ms  > 0 else "       -"
        spd  = f"{r.best_mbps:>9.2f}"  if r.best_mbps > 0 else "        -"
        sc   = f"{r.score:>6.1f}"      if r.score   > 0 else "     -"
        colo = r.colo or "  -"
        print(f"{rank:>4}  {r.ip:<16}  {lat}  {spd}  {sc}  {colo:>5}")
    if len(alive_results) > 20:
        print(f"  ... and {len(alive_results) - 20} more alive configs")
    print(f"{'=' * 75}")

    # ── Write outputs ─────────────────────────────────────────────────────────
    write_outputs(ordered_uris, elapsed, total_input)


def main():
    p = argparse.ArgumentParser(
        description="Filter & rank V2Ray configs by latency + speed, then update output/",
    )
    p.add_argument("--input",  "-i", help=f"Input file (default: {INPUT_FILE})")
    p.add_argument("--mode",   "-m",
                   choices=["quick", "normal", "thorough"], default="quick",
                   help="Scan preset (default: quick — fastest for CI)")
    p.add_argument("--skip-download", action="store_true",
                   help="Latency-only mode — no download speed test")
    p.add_argument("--workers",       type=int,   default=LATENCY_WORKERS)
    p.add_argument("--speed-workers", type=int,   default=SPEED_WORKERS)
    p.add_argument("--timeout",       type=float, default=LATENCY_TIMEOUT)
    p.add_argument("--speed-timeout", type=float, default=SPEED_TIMEOUT)
    args = p.parse_args()

    try:
        asyncio.run(run_filter(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
