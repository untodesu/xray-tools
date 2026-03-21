#!/usr/bin/env python3

# Reads VLESS URLs from a provided file, parses them
# and replaces balancer outbounds in xray config with
# the parsed ones + direct/block, sets up balancer and observatory
# then saves and restarts xray.service
#
# Supported VLESS params:
#   security=reality|tls|none   transport security layer
#   type=tcp|ws|grpc|http|h2    transport network type
#   flow=xtls-rprx-vision       XTLS flow (optional)
#   sni, fp, pbk, sid, spx      Reality/TLS options
#   path, host                  WS / HTTP/2 options
#   serviceName                 gRPC service name
#   headerType                  TCP header obfuscation
#
# Usage:
#   xray-balancer.py [--links PATH] [--config PATH] [--dry-run]
#
# Default paths:
#   --links   /usr/local/share/xray/links.txt
#   --config  /usr/local/etc/xray/config.json
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
from urllib.parse import urlparse, parse_qs, unquote

LINKS_PATH = Path("/usr/local/share/xray/links.txt")
CONFIG_PATH = Path("/usr/local/etc/xray/config.json")

## Parses vless://<uuid>@<host>:<port>?params#tag
## and returns a ready-to-use outbound dict for xray config
def parse_vless_link(link: str) -> dict | None:
    link = link.rstrip()

    if not link or link.startswith("#"):
        return None # skip empty lines and comments

    match = re.match(r"^vless://([^@]+)@([^:]+):(\d+)\??([^#]*)#?(.*)?$", link)

    if not match:
        return None # invalid format but go silently because I don't want cron filling my inbox with errors

    uuid = match.group(1)
    host = match.group(2)
    port = int(match.group(3))
    query_str = match.group(4)
    fragment = unquote(match.group(5) or "")

    params = parse_qs(query_str)
    p = lambda key, default="": params.get(key, [default])[0]

    # tag: either from fragment or host:port
    tag = fragment if fragment else f"{host}:{port}"
    tag = re.sub(r"[^a-zA-Z0-9@._-]", "_", tag)

    # Basic outbound
    outbound = {
        "tag": tag,
        "protocol": "vless",
        "settings": {
            # xray-core uses "vnext" as the key for VLESS outbound peers
            "vnext": [{
                "address": host,
                "port": port,
                "users": [{
                    "id": uuid,
                    "encryption": p("encryption", "none"),
                }]
            }]
        },
        "streamSettings": {
            # xray uses "http" for both http and h2 network types
            "network": "http" if p("type", "tcp") == "h2" else p("type", "tcp"),
        }
    }

    # Flow (XTLS Vision)
    flow = p("flow")
    if flow:
        outbound["settings"]["vnext"][0]["users"][0]["flow"] = flow

    # Security
    security = p("security", "none")
    outbound["streamSettings"]["security"] = security

    if security == "reality":
        outbound["streamSettings"]["realitySettings"] = {}
        rs = outbound["streamSettings"]["realitySettings"]
        if p("sni"):
            rs["serverName"] = p("sni")
        if p("fp"):
            rs["fingerprint"] = p("fp")
        if p("pbk"):
            rs["publicKey"] = p("pbk")
        if p("sid"):
            rs["shortId"] = p("sid")
        if p("spx"):
            rs["spiderX"] = p("spx")
    elif security == "tls":
        outbound["streamSettings"]["tlsSettings"] = {}
        ts = outbound["streamSettings"]["tlsSettings"]
        if p("sni"):
            ts["serverName"] = p("sni")
        if p("fp"):
            ts["fingerprint"] = p("fp")
        if p("alpn"):
            ts["alpn"] = p("alpn").split(",")

    # Transport (normalize h2 → http, xray uses "http" for both)
    network = p("type", "tcp")
    if network == "h2":
        network = "http"

    if network == "ws":
        outbound["streamSettings"]["wsSettings"] = { "path": p("path", "/") }
        ws_host = p("host")
        if ws_host:
            outbound["streamSettings"]["wsSettings"]["headers"] = {"Host": ws_host}
    elif network == "grpc":
        outbound["streamSettings"]["grpcSettings"] = { "serviceName": p("serviceName", "") }
    elif network == "tcp":
        header_type = p("headerType", "none")
        if header_type != "none":
            outbound["streamSettings"]["tcpSettings"] = { "header": {"type": header_type} }
    elif network == "http":
        outbound["streamSettings"]["httpSettings"] = { "path": p("path", "/") }
        h2_host = p("host")
        if h2_host:
            outbound["streamSettings"]["httpSettings"]["host"] = h2_host.split(",")

    return outbound

# Updates the config
def update_config(config: dict, outbounds: list[dict]) -> dict:
    proxy_tags = [ob["tag"] for ob in outbounds]

    service_outbounds = [
        {"tag": "direct", "protocol": "freedom"},
        {"tag": "block", "protocol": "blackhole"},
    ]

    config["outbounds"] = outbounds + service_outbounds

    # Balancer
    config["routing"]["balancers"] = [{
        "tag": "proxy-balancer",
        "selector": proxy_tags,
        "strategy": {"type": "leastPing"},
    }]

    # Observatory
    config["observatory"] = {
        "subjectSelector": proxy_tags,
        "probeInterval": "5m",
        "probeURL": "https://www.google.com/generate_204",
    }

    # Replace outboundTag with balancerTag in routing rules
    for rule in config["routing"].get("rules", []):
        if rule.get("outboundTag") == "proxy":
            del rule["outboundTag"]
            rule["balancerTag"] = "proxy-balancer"
    
    return config

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--links", type=Path, default=LINKS_PATH)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Don't save or restart")
    args = parser.parse_args()

    if not args.links.exists():
        print(f"links file not found: {args.links}", file=sys.stderr)
        sys.exit(1)

    links = args.links.read_text().strip().splitlines()
    outbounds = []
    seen_tags = set()

    for link in links:
        ob = parse_vless_link(link)
        if ob:
            if ob["tag"] in seen_tags:
                continue
            seen_tags.add(ob["tag"])
            outbounds.append(ob)

    if not outbounds:
        print("no valid VLESS links found", file=sys.stderr)
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
