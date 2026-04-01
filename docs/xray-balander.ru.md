# Обновлятор inbound-ов: _xray-balancer.py_

У меня есть _несколько_ VPS-ок с иксреем, и inbound-ы на них хочется управлять динамически через директорию с JSON-файлами.

## Как это работает

Скрипт читает все `.json` файлы из `--inbounds-dir` (по умолчанию: `/usr/local/share/xray/inbounds.d/`), считает каждый валидным объектом inbound-а xray и заменяет массив `inbounds` в конфиге на загруженные. Затем сохраняет конфиг и перезапускает `xray.service`.

Файлы обрабатываются в алфавитном порядке

## Использование

```
xray-balancer.py [--inbounds-dir PATH] [--config PATH] [--dry-run]
```

| Флаг | Значение по умолчанию |
|------|-----------------------|
| `--inbounds-dir` | `/usr/local/share/xray/inbounds.d/` |
| `--config` | `/usr/local/etc/xray/config.json` |
| `--dry-run` | выводит результат в stdout, без сохранения и перезапуска |

## Установка
1. Куда-нибудь скачиваем  
2. Chmod-аем его по самые +x пермы  
3. Кладём JSON-файлы inbound-ов в `/usr/local/share/xray/inbounds.d/`  
4. Кроним скрипт  

## Пример crontab

```
0 */6 * * * /usr/local/bin/xray-balancer.py
```

## Ссылки
```
https://raw.githubusercontent.com/untodesu/xray-tools/refs/heads/main/scripts/xray-balancer.py
```
