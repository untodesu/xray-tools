# Прозрачный прокси для  WG - _xray-tproxy-xxxx.sh_

У меня крутится домашний (одомашненный) сервер и иногда надо _некоторые_ вещи с телефона, который к нему подключается, пропускать через Xray. Для этого у иксрея нуженн outbound вроде такого:

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

## Установка
1. Качаем и/или копируем куда-нибудь  
2. Редактируем так, чтобы соответствало конфигу WireGuard'а  
3. Вписываем вызовы скриптов в PostUp и PostDown  

### Прямые ссылки
```
https://raw.githubusercontent.com/untodesu/xray-tools/refs/heads/main/scripts/xray-tproxy-setup.sh
```
```
https://raw.githubusercontent.com/untodesu/xray-tools/refs/heads/main/scripts/xray-tproxy-teardown.sh
```
