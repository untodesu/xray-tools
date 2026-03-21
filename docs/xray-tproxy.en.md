# Transparent proxy for WG - _xray-tproxy-xxxx.sh_

I run a homelab server and there is need for some stuff passed through WireGuard to be passed through Xray. It requires an outbound of this sort:  

```json
"inbounds": [
  ...
  {
    "tag": "tproxy-in",
    "protocol": "dokodemo-door",
    "listen": "0.0.0.0",
    "port": 12345,
    "settings": {
      "network": "tcp,udp",
      "followRedirect": true
    },
    "sniffing": {
      "enabled": true,
      "destOverride": ["http", "tls"]
    },
    "streamSettings": {
      "sockopt": {
        "tproxy": "tproxy"
      }
    }
  }
  ...
]
```

## Installation

1. Copy somewhere  
2. Edit to fit your needs  
3. Put calls into PostUp and PostDown  
