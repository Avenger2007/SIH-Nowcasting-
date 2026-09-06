"""
scripts/collect_frames.py
Build the INSAT frame buffer so cloud motion becomes available.

The public MOSDAC gallery serves only the newest scan per product, so a motion
estimate needs frames accumulated over time. Run this on a schedule - the
INSAT-3D imager completes a full disk every 30 minutes, so every 15 minutes
catches each scan without hammering the endpoint.

    # once
    python scripts/collect_frames.py

    # keep collecting
    python scripts/collect_frames.py --watch --interval 900

    # Windows Task Scheduler / cron every 15 minutes
    schtasks /create /tn INSATCollect /tr "python C:\\path\\collect_frames.py" ^
             /sc minute /mo 15
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.datasources import mosdac
from utils.datasources.base import SourceStatus


def collect_once(channels) -> int:
    """Fetch each channel once. Returns the number of NEW distinct scans."""
    before = mosdac.buffer_status()["total_frames"]

    for channel in channels:
        result = mosdac.fetch_channel(channel)
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        if result.status == SourceStatus.LIVE:
            print(f"  [{stamp}] {channel:<8} ok   {result.message}")
        else:
            print(f"  [{stamp}] {channel:<8} {result.status.value}  "
                  f"{result.message[:80]}")

    after = mosdac.buffer_status()
    gained = after["total_frames"] - before

    print(f"  buffer: {after['total_frames']} frames "
          f"({gained:+d} new)  {after['channels']}")
    return gained


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channels", nargs="+", default=["IR1"],
                        help="INSAT channels to collect (default: IR1)")
    parser.add_argument("--watch", action="store_true",
                        help="keep collecting on an interval")
    parser.add_argument("--interval", type=int, default=900,
                        help="seconds between collections (default 900)")
    args = parser.parse_args()

    unknown = [c for c in args.channels if c not in mosdac.CHANNELS]
    if unknown:
        print(f"Unknown channel(s): {unknown}. "
              f"Available: {', '.join(mosdac.CHANNELS)}")
        return 2

    print(f"Collecting {', '.join(args.channels)} from MOSDAC")
    print(f"Buffer directory: {mosdac.FRAME_BUFFER_DIR}\n")

    if not args.watch:
        collect_once(args.channels)
        return 0

    print(f"Watching every {args.interval}s. Ctrl+C to stop.\n")
    try:
        while True:
            collect_once(args.channels)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
