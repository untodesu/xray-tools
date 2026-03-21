#!/bin/bash
# xray-tproxy-setup.sh - redirect wgX traffic into xray
# so it's essentially a transparent-proxy; must be run
# after wgX is up [can be added as a PostUp step in config]

set -e

WG_PORT=33742
TPROXY_PORT=12345
MARK=1
TABLE=100
DEVICE="wg0"

# Routing table for marked packets
ip rule add fwmark ${MARK} table ${TABLE} 2>/dev/null || true
ip route add local 0.0.0.0/0 dev lo table ${TABLE} 2>/dev/null || true

# nftables
nft -f - <<'EOF'
table ip xray {
  chain prerouting {
    type filter hook prerouting priority mangle; policy accept;

    # Don't touch traffic to the server itself (WireGuard port)
    udp dport ${WG_PORT} accept

    # Don't touch local addresses
    ip daddr 10.66.66.0/24 accept
    ip daddr 127.0.0.0/8 accept
    ip daddr 192.168.0.0/16 accept
    ip daddr 172.16.0.0/12 accept
    ip daddr 10.0.0.0/8 accept

    # All TCP/UDP from ${DEVICE} -> tproxy
    iifname "${DEVICE}" meta l4proto tcp tproxy to :${TPROXY_PORT} meta mark set ${MARK}
    iifname "${DEVICE}" meta l4proto udp tproxy to :${TPROXY_PORT} meta mark set ${MARK}
  }
}
EOF

echo "tproxy rules applied"
