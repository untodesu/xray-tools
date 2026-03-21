# Server boostrap: _xray-bootstrap.py_

## Features
- Allows for general-purpose maintenance for existing scripts, JSON is parsed, modified and saved to disk without making a new table, so **invalid JSON configurations will probably remain invalid after the script works through them**;  
- Non-intrusive: the script, unless demanded explicitly by the user, stores and manages its own specific cofiguration - `xrboot.json` and hence a separate daemon service - `xray@xrboot.service` so you can semi-easily get rid of its configuration if you want;  
- Generates proxy URL dumps in CSV format;  
- Somewhat intuitive to use, I guess...  

## Prerequisites
- [Xray-core](https://github.com/XTLS/Xray-core);  
- [cURL](https://curl.se/);  
- [Python3](https://www.python.org/);  

## Usage

### 1. Install xray-core

Most of the time you'd need to run this command but I'd also recommend you to go through [documentation](https://github.com/XTLS/Xray-install) and figure out what is best for you specifically  

```bash
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
```

### 2. Run the script

```bash
python3 <(curl https://raw.githubusercontent.com/untodesu/xray-tools/refs/heads/main/scripts/xray-bootstrap.py)
```

### 3. Navigate via curses-based GUI

Then there's a curses-based GUI/TUI that would guide you through setting up VLESS inbounds (there is no other preset available at the time of writing this)  

![One of initial setup screens of the script](/media/xray-bootstrap.png)

### 4. ?????

### 5. PROFIT!
