#!/bin/bash
# xray-tproxy-teardown.sh - remove tproxy rules;
# must be run after wgX is down [can be added as a PostDown step in config]

MARK=1
TABLE=100

nft delete table ip xray 2>/dev/null || true
ip rule del fwmark ${MARK} table ${TABLE} 2>/dev/null || true
ip route del local 0.0.0.0/0 dev lo table ${TABLE} 2>/dev/null || true

echo "tproxy rules removed"
