# Inbound updater: _xray-balancer.py_

I have a good bunch of VPS-es with xray-core set up and I'd like to manage all their inbounds dynamically from a directory of JSON files.

## How it works

The script reads every `.json` file from `--inbounds-dir` (default: `/usr/local/share/xray/inbounds.d/`), treats each as a valid xray inbound object, and replaces the `inbounds` array in the xray config with the loaded ones. It then saves the config and restarts `xray.service`.

Files are processed in alphabetical order

## Usage

```
xray-balancer.py [--inbounds-dir PATH] [--config PATH] [--dry-run]
```

| Flag | Default |
|------|---------|
| `--inbounds-dir` | `/usr/local/share/xray/inbounds.d/` |
| `--config` | `/usr/local/etc/xray/config.json` |
| `--dry-run` | prints result to stdout, no save/restart |

## Installation
1. Download somewhere  
2. Chmod with executable perms it  
3. Place inbound JSON files in `/usr/local/share/xray/inbounds.d/`  
4. Cron the script  

## Crontab example

```
0 */6 * * * /usr/local/bin/xray-balancer.py
```

## Direct links
```
https://raw.githubusercontent.com/untodesu/xray-tools/refs/heads/main/scripts/xray-balancer.py
```
