"""Standalone updater: wait for the application, then run a verified installer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from update_service import UpdateError, _verify_authenticode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("installer")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--publisher", required=True)
    parser.add_argument("--health-marker", required=True)
    args = parser.parse_args()
    installer = Path(args.installer).resolve()
    if not installer.is_file() or installer.suffix.lower() != ".exe":
        return 2
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    if digest.lower() != args.sha256.lower():
        return 3
    try:
        _verify_authenticode(installer, args.publisher)
    except UpdateError:
        return 3
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            os.kill(args.pid, 0)
        except OSError:
            break
        time.sleep(0.5)
    else:
        return 4
    try:
        completed = subprocess.run([str(installer), "/NORESTART"], check=False)
    except OSError:
        return 5
    if completed.returncode != 0:
        return completed.returncode
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            with open(args.health_marker, "r", encoding="utf-8") as marker_file:
                if json.load(marker_file).get("status") == "healthy":
                    return 0
        except (OSError, ValueError):
            pass
        time.sleep(1)
    try:
        with open(args.health_marker, "w", encoding="utf-8") as marker_file:
            json.dump({"status": "health-check-failed", "installer": str(installer)}, marker_file)
    except OSError:
        pass
    return 6


if __name__ == "__main__":
    sys.exit(main())
