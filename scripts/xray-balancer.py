#!/usr/bin/env python3

# Reads outbound configs from:
#   - /usr/local/share/xray/outbounds.d/*.json       (one outbound per file)
#   - /usr/local/share/xray/outbounds.d/*.json.list  (one JSON object per line)
# Replaces balancer outbounds in xray config, sets up balancer and observatory,
# then saves and restarts xray.service
#
# Usage:
#   xray-balancer.py [--outbounds-dir PATH] [--config PATH] [--dry-run]
#
# Default paths:
#   --outbounds-dir  /usr/local/share/xray/outbounds.d
#   --config         /usr/local/etc/xray/config.json
#
# --dry-run prints the resulting config to stdout without saving or restarting.
#
# Crontab entry for doing that every 6 hours:
#   0 */6 * * * /usr/local/bin/xray-balancer.py

import json
import shutil
import subprocess
import sys
import re
from pathlib import Path

OUTBOUNDS_DIR = Path("/usr/local/share/xray/outbounds.d")
CONFIG_PATH = Path("/usr/local/etc/xray/config.json")


def sanitize_tag(tag: str) -> str:
    return re.sub(r"[^a-zA-Z0-9@._-]", "_", tag)


def load_outbound(data: dict, source: str) -> dict | None:
    if not isinstance(data, dict):
        print(f"warning: skipping non-object entry in {source}", file=sys.stderr)
        return None
    if "tag" not in data:
        print(f"warning: skipping outbound without 'tag' in {source}", file=sys.stderr)
        return None
    if "protocol" not in data:
        print(f"warning: skipping outbound without 'protocol' in {source}", file=sys.stderr)
        return None
    data["tag"] = sanitize_tag(data["tag"])
    return data


def load_outbounds_from_dir(directory: Path) -> list[dict]:
    outbounds = []
    seen_tags = set()

    if not directory.exists():
        print(f"outbounds directory not found: {directory}", file=sys.stderr)
        sys.exit(1)

    # Collect and sort files for deterministic ordering
    json_files = sorted(directory.glob("*.json"))
    list_files = sorted(directory.glob("*.json.list"))

    for path in json_files:
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            print(f"warning: failed to parse {path}: {e}", file=sys.stderr)
            continue

        ob = load_outbound(data, str(path))
        if ob and ob["tag"] not in seen_tags:
            seen_tags.add(ob["tag"])
            outbounds.append(ob)

    for path in list_files:
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"warning: {path}:{lineno}: {e}", file=sys.stderr)
                continue

            ob = load_outbound(data, f"{path}:{lineno}")
            if ob and ob["tag"] not in seen_tags:
                seen_tags.add(ob["tag"])
                outbounds.append(ob)

    return outbounds


def update_config(config: dict, outbounds: list[dict]) -> dict:
    proxy_tags = [ob["tag"] for ob in outbounds]

    service_outbounds = [
        {"tag": "direct", "protocol": "freedom"},
        {"tag": "block", "protocol": "blackhole"},
    ]

    config["outbounds"] = outbounds + service_outbounds

    config["routing"]["balancers"] = [{
        "tag": "proxy-balancer",
        "selector": proxy_tags,
        "strategy": {
            "type": "leastLoad",
            "settings": {
                "baselines": ["400ms"],
                "expected": 1,
                "maxRTT": "2000ms",
                "tolerance": 0.5
            }
        },
    }]

    config["observatory"] = {
        "subjectSelector": proxy_tags,
        "probeInterval": "5m",
        "probeURL": "https://www.google.com/generate_204",
    }

    for rule in config["routing"].get("rules", []):
        if rule.get("outboundTag") == "proxy":
            del rule["outboundTag"]
            rule["balancerTag"] = "proxy-balancer"

    return config


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--outbounds-dir", type=Path, default=OUTBOUNDS_DIR)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Don't save or restart")
    args = parser.parse_args()

    outbounds = load_outbounds_from_dir(args.outbounds_dir)

    if not outbounds:
        print("no valid outbounds found", file=sys.stderr)
        sys.exit(1)

    if not args.config.exists():
        print(f"config file not found: {args.config}", file=sys.stderr)
        sys.exit(2)

    config = json.loads(args.config.read_text())
    config = update_config(config, outbounds)

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
