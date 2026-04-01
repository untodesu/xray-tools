#!/usr/bin/env python3

# Reads outbound JSONs from a provided directory,
# parses them and replaces the outbounds array in xray config,
# then saves the config and restarts xray.service
#
# Each .json file in the directory must be a valid xray outbound object
#
# Usage:
#   xray-balancer.py [--outbounds-dir PATH] [--config PATH] [--dry-run]
#
# Default paths:
#   --outbounds-dir /usr/local/share/xray/outbounds.d/
#   --config        /usr/local/etc/xray/config.json
#
# --dry-run prints the resulting config to stdout without saving or restarting.
#
# Crontab entry for doing that every 6 hours:
#   0 */6 * * * /usr/local/bin/xray-balancer.py

import json
import shutil
import subprocess
import sys
from pathlib import Path

OUTBOUNDS_DIR = Path("/usr/local/share/xray/outbounds.d/")
CONFIG_PATH = Path("/usr/local/etc/xray/config.json")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--outbounds-dir", type=Path, default=OUTBOUNDS_DIR)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Don't save or restart")
    args = parser.parse_args()

    if not args.outbounds_dir.exists():
        print(f"outbounds directory not found: {args.outbounds_dir}", file=sys.stderr)
        sys.exit(1)

    outbounds = []
    seen_tags = set()

    all_paths = sorted(args.outbounds_dir.glob("*.json")) + sorted(args.outbounds_dir.glob("*.json.list"))

    for path in all_paths:
        if path.suffix == ".list":
            candidates = []
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    candidates.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"skipping {path.name} line {lineno}: invalid JSON: {e}", file=sys.stderr)
        else:
            try:
                candidates = [json.loads(path.read_text())]
            except json.JSONDecodeError as e:
                print(f"skipping {path.name}: invalid JSON: {e}", file=sys.stderr)
                continue

        for outbound in candidates:
            tag = outbound.get("tag", path.stem)

            if tag in seen_tags:
                original_tag = tag
                counter = 2
                while tag in seen_tags:
                    tag = f"{original_tag}_{counter}"
                    counter += 1
                print(f"renaming duplicate tag '{original_tag}' to '{tag}' in {path.name}", file=sys.stderr)
                outbound["tag"] = tag

            seen_tags.add(tag)
            outbounds.append(outbound)

    if not outbounds:
        print("no valid outbound JSONs found", file=sys.stderr)
        sys.exit(1)

    if not args.config.exists():
        print(f"config file not found: {args.config}", file=sys.stderr)
        sys.exit(2)

    config = json.loads(args.config.read_text())
    config["outbounds"] = outbounds

    if args.dry_run:
        print(json.dumps(config, indent=2, ensure_ascii=False))
        sys.exit(0)

    backup = args.config.with_suffix(".json.old")
    shutil.copy2(args.config, backup)

    args.config.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    result = subprocess.run(["/usr/bin/systemctl", "restart", "xray"], capture_output=True, text=True)

    if result.returncode == 0:
        sys.exit(0)
    else:
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
