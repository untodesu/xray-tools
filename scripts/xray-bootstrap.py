#!/usr/bin/env python3

import curses
import json
import os
import random
import re
import shutil
import subprocess
import sys
import urllib.request

VERSION = "1.0.0"

REQUIRED_BINARIES = [
    "xray",
    "openssl",
    "systemctl",
    "sleep",
]

MIN_XRAY_VERSION = "25.12.2"

VLESS_SNI_PREDEFS = [
    "www.microsoft.com",
    "download.microsoft.com",
    "packages.microsoft.com",
    "download.lineageos.org",
    "raw.githubusercontent.com",
    "dl.google.com",
    "update.googleapis.com",
    "releases.ubuntu.com",
    "speed.cloudflare.com",
]

PORT_PREDEFS = [
    443,
    8443,
]

IPGETTER_PROTOS = ["http", "https"]
IPGETTER_HOSTS = ["checkip.amazonaws.com", "eth0.me", "ifconfig.me", "ipecho.net/plain", "icanhazip.com", "api.ipify.org", "ipinfo.io/ip"]
SERVER_ADDRESS = ""

for protocol in IPGETTER_PROTOS:
    if len(SERVER_ADDRESS) > 0:
        break

    print(f"Getting server IP, using HTTP")
    
    for host in IPGETTER_HOSTS:
        try:
            sys.stdout.write(f"\tTrying {host}...")
            address = urllib.request.urlopen(f"{protocol}://{host}").read().decode("utf-8").rstrip()
            SERVER_ADDRESS = address
            sys.stdout.write("OK!\n")
            break
        except:
            sys.stdout.write(f"FAILED!\n")
            SERVER_ADDRESS = ""

assert len(SERVER_ADDRESS) > 0, "Failed to get server address!!!!"

class UU_InputMenu:
    def __init__(self, screen, prompt, default_value=""):
        self.screen = screen
        self.prompt = prompt
        self.default_value = default_value

    def get(self):
        curses.curs_set(1) # show cursor
        curses.echo(True)

        while True:
            self.screen.clear()
            self.screen.addstr(0, 0, self.prompt)

            if self.default_value:
                self.screen.addstr(2, 0, f"Default: {self.default_value}", curses.A_DIM)
            self.screen.addstr(5, 0, ">>")
            self.screen.refresh()

            try:
                result = self.screen.getstr(5, 3, 60).decode("utf-8")
            except curses.error:
                result = self.default_value

            if 0 == len(result):
                if 0 == len(self.default_value):
                    continue
                return self.default_value
            return result

class UU_ChoiceMenu:
    def __init__(self, screen, prompt):
        self.screen = screen
        self.prompt = prompt
        self.choices = []
        self.default_index = 0

    def add_choice(self, choice, is_default=False):
        self.choices.append(choice)
        if is_default:
            self.default_index = len(self.choices) - 1

    def add_separator(self):
        self.choices.append(None)

    def size(self):
        return len(self.choices)

    def get(self):
        while self.default_index < len(self.choices) and self.choices[self.default_index] is None:
            self.default_index += 1
        if self.default_index >= len(self.choices):
            raise ValueError("No valid choices provided")

        selection = self.default_index

        curses.curs_set(0) # hide cursor
        curses.echo(False)

        while True:
            self.screen.clear()
            self.screen.addstr(0, 0, self.prompt)

            for i, choice in enumerate(self.choices):
                if self.choices[i]:
                    if i == selection:
                        self.screen.addstr(i + 4, 0, ">>")
                        self.screen.addstr(i + 4, 3, str(choice), curses.A_REVERSE)
                    else:
                        self.screen.addstr(i + 4, 3, str(choice))

            self.screen.refresh()

            key = self.screen.getch()

            if key == curses.KEY_UP and selection > 0:
                while selection > 0:
                    selection -= 1
                    if self.choices[selection]:
                        break
            elif key == curses.KEY_DOWN and selection < len(self.choices) - 1:
                while selection < len(self.choices) - 1:
                    selection += 1
                    if self.choices[selection]:
                        break
            elif key == curses.KEY_ENTER or key == 10 or key == 13:
                break

        return selection

class UU_MessageBox:
    def __init__(self, screen, message):
        self.screen = screen
        self.message = message

    def show(self):
        choice_menu = UU_ChoiceMenu(self.screen, self.message)
        choice_menu.add_choice("OK", is_default=True)
        choice_menu.get()

class UU_YesNoBox:
    def __init__(self, screen, message, default_yes=True):
        self.screen = screen
        self.message = message
        self.default_yes = default_yes

    def get(self):
        choice_menu = UU_ChoiceMenu(self.screen, self.message)
        choice_menu.add_choice("Yes", is_default=self.default_yes)
        choice_menu.add_choice("No", is_default=not self.default_yes)
        return 0 == choice_menu.get()

def xrb_make_vless_url(xray_inbound, xray_client, client_index):
    port = xray_inbound["port"]
    sni = xray_inbound["streamSettings"]["realitySettings"]["serverNames"][0]
    private_key = xray_inbound["streamSettings"]["realitySettings"]["privateKey"]

    # Xray developers think it's a GOOD and FUNNY idea to change the way
    # stuff is outputted per major release. So say, for version 26.2.6 it's
    # just "Password: <key>" but for 26.3.27 it's "Password (PublicKey): <key>"
    # ⠉⠉⠉⣿⡿⠿⠛⠋⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⣻⣩⣉⠉⠉
    # ⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⢀⣀⣀⣀⣀⣀⣀⡀⠄⠄⠉⠉⠄⠄⠄
    # ⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⣠⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣤⠄⠄⠄⠄
    # ⠄⠄⠄⠄⠄⠄⠄⠄⠄⢤⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠄⠄⠄
    # ⡄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠉⠄⠉⠉⠉⣋⠉⠉⠉⠉⠉⠉⠉⠉⠙⠛⢷⡀⠄⠄
    # ⣿⡄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠠⣾⣿⣷⣄⣀⣀⣀⣠⣄⣢⣤⣤⣾⣿⡀⠄
    # ⣿⠃⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⣹⣿⣿⡿⠿⣿⣿⣿⣿⣿⣿⣿⣿⢟⢁⣠
    # ⣿⣿⣄⣀⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠉⠉⣉⣉⣰⣿⣿⣿⣿⣷⣥⡀⠉⢁⡥⠈
    # ⣿⣿⣿⢹⣇⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠒⠛⠛⠋⠉⠉⠛⢻⣿⣿⣷⢀⡭⣤⠄
    # ⣿⣿⣿⡼⣿⠷⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⢀⣀⣠⣿⣟⢷⢾⣊⠄⠄
    # ⠉⠉⠁⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠈⣈⣉⣭⣽⡿⠟⢉⢴⣿⡇⣺⣿⣷
    # ⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠁⠐⢊⣡⣴⣾⣥⣿⣿⣿

    xray_x25519_raw = subprocess.check_output(["xray", "x25519", "-i", private_key], text=True).rstrip().strip()
    xray_x25519_lines = xray_x25519_raw.split("\n")
    xray_x25519_password_line = next(line for line in xray_x25519_lines if "Password" in line or "PublicKey" in line)
    assert xray_x25519_password_line, "Failed to get public key from xray x25519 output"
    public_key = xray_x25519_password_line.split(":", 1)[1].strip()

    short_id = xray_inbound["streamSettings"]["realitySettings"]["shortIds"][client_index]
    client_flow = xray_client.get("flow", "xtls-rprx-vision")
    client_uuid = xray_client["id"]

    url = f"vless://{client_uuid}@{SERVER_ADDRESS}:{port}?"
    url += f"security=reality&sni={sni}&alpn=h2&"
    url += f"fp=chrome&pbk={public_key}&sid={short_id}&"
    url += f"type=tcp&flow={client_flow}&encryption=none#"
    url += xray_client["email"].replace(' ', '%20')

    return url

def xrb_make_client_url(xray_inbound, xray_client, client_index):
    if xray_inbound["protocol"] == "vless":
        return xrb_make_vless_url(xray_inbound, xray_client, client_index)
    return None

def xrb_edit_client_email(screen, xray_inbound, xray_client):
    menu = UU_InputMenu(screen, "Client email", xray_client["email"])
    new_client_email = menu.get().strip()

    if new_client_email.endswith("@"):
        new_client_email += xray_inbound["tag"]

    xray_client["email"] = new_client_email

    return xray_client

def xrb_edit_client_flow_vless(screen, xray_client):
    menu = UU_ChoiceMenu(screen, "Select flow")
    menu.add_choice("xtls-rprx-vision", is_default=(xray_client.get("flow", "") == "xtls-rprx-vision"))
    menu.add_choice("none", is_default=(xray_client.get("flow", "") == "none"))
    xray_client["flow"] = menu.choices[menu.get()]
    return xray_client

def xrb_edit_client(screen, xray_inbound, xray_client, client_index):
    menu = UU_ChoiceMenu(screen, "Manage client")
    menu.add_choice("Get URL")
    menu.add_choice("Get outbound JSON")
    menu.add_separator()
    menu.add_choice("Change email")

    if xray_inbound["protocol"] == "vless":
        menu.add_choice("Change flow")

    menu.add_separator()
    menu.add_choice("Remove")
    menu.add_separator()
    menu.add_choice("Back")

    choice = menu.get()

    if choice == 0: # Get URL
        msgbox = UU_MessageBox(screen, xrb_make_client_url(xray_inbound, xray_client, client_index))
        msgbox.show()
        return xray_client

    if choice == 1: # Get outbound JSON
        path = UU_InputMenu(screen, "Enter file path", f"{xray_client.get('email', f'client{client_index}')}_outbound.json").get()
        outbound = xrb_make_client_outbound(xray_inbound, xray_client, client_index)
        with open(path, "w") as f:
            f.write(json.dumps(outbound, indent=2, ensure_ascii=False))
        UU_MessageBox(screen, f"Outbound saved to {path}").show()
        return xray_client

    if choice == 3: # Change email
        xray_client = xrb_edit_client_email(screen, xray_inbound, xray_client)
        return xray_client

    if xray_inbound["protocol"] == "vless" and choice == 4: # Change flow
        xray_client = xrb_edit_client_flow_vless(screen, xray_client)
        return xray_client

    if choice == menu.size() - 3: # Remove
        if UU_YesNoBox(screen, "Are you sure you want to remove this client?", default_yes=False).get():
            return None

    if choice == menu.size() - 1: # Back
        return xray_client

    return xray_client

def xrb_create_client(screen, xray_inbound):
    client_index = len(xray_inbound["settings"]["clients"])

    email_menu = UU_InputMenu(screen, "Client email", f"client{client_index}@{xray_inbound['tag']}")
    email = email_menu.get()

    if email.endswith("@"):
        email += xray_inbound["tag"]

    client = {}
    client["id"] = subprocess.check_output(["xray", "uuid"], text=True).rstrip()
    client["email"] = email

    if xray_inbound["protocol"] == "vless":
        flow_menu = UU_ChoiceMenu(screen, "Select flow")
        flow_menu.add_choice("xtls-rprx-vision", is_default=True)
        flow_menu.add_choice("none")
        flow = flow_menu.choices[flow_menu.get()]
        client["flow"] = flow

    xray_inbound["settings"]["clients"].append(client)

    if xray_inbound["protocol"] == "vless":
        short_id = subprocess.check_output(["openssl", "rand", "-hex", "8"], text=True).rstrip()
        xray_inbound["streamSettings"]["realitySettings"]["shortIds"].append(short_id)

    return xray_inbound

def xrb_make_vless_outbound(xray_inbound, xray_client, client_index):
    port = xray_inbound["port"]
    sni = xray_inbound["streamSettings"]["realitySettings"]["serverNames"][0]
    private_key = xray_inbound["streamSettings"]["realitySettings"]["privateKey"]

    # Xray developers think it's a GOOD and FUNNY idea to change the way
    # stuff is outputted per major release. So say, for version 26.2.6 it's
    # just "Password: <key>" but for 26.3.27 it's "Password (PublicKey): <key>"
    # ⠉⠉⠉⣿⡿⠿⠛⠋⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⣻⣩⣉⠉⠉
    # ⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⢀⣀⣀⣀⣀⣀⣀⡀⠄⠄⠉⠉⠄⠄⠄
    # ⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⣠⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣤⠄⠄⠄⠄
    # ⠄⠄⠄⠄⠄⠄⠄⠄⠄⢤⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠄⠄⠄
    # ⡄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠉⠄⠉⠉⠉⣋⠉⠉⠉⠉⠉⠉⠉⠉⠙⠛⢷⡀⠄⠄
    # ⣿⡄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠠⣾⣿⣷⣄⣀⣀⣀⣠⣄⣢⣤⣤⣾⣿⡀⠄
    # ⣿⠃⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⣹⣿⣿⡿⠿⣿⣿⣿⣿⣿⣿⣿⣿⢟⢁⣠
    # ⣿⣿⣄⣀⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠉⠉⣉⣉⣰⣿⣿⣿⣿⣷⣥⡀⠉⢁⡥⠈
    # ⣿⣿⣿⢹⣇⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠒⠛⠛⠋⠉⠉⠛⢻⣿⣿⣷⢀⡭⣤⠄
    # ⣿⣿⣿⡼⣿⠷⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⢀⣀⣠⣿⣟⢷⢾⣊⠄⠄
    # ⠉⠉⠁⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠈⣈⣉⣭⣽⡿⠟⢉⢴⣿⡇⣺⣿⣷
    # ⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠁⠐⢊⣡⣴⣾⣥⣿⣿⣿

    xray_x25519_raw = subprocess.check_output(["xray", "x25519", "-i", private_key], text=True).rstrip().strip()
    xray_x25519_lines = xray_x25519_raw.split("\n")
    xray_x25519_password_line = next(line for line in xray_x25519_lines if "Password" in line or "PublicKey" in line)
    assert xray_x25519_password_line, "Failed to get public key from xray x25519 output"
    public_key = xray_x25519_password_line.split(":", 1)[1].strip()

    short_id = xray_inbound["streamSettings"]["realitySettings"]["shortIds"][client_index]

    outbound = {}
    outbound["tag"] = xray_client.get("email", f"client{client_index}")
    outbound["protocol"] = "vless"
    outbound["settings"] = {
        "vnext": [{
            "address": SERVER_ADDRESS,
            "port": port,
            "users": [{
                "id": xray_client["id"],
                "flow": xray_client.get("flow", "xtls-rprx-vision"),
                "encryption": "none"
            }]
        }]
    }
    outbound["streamSettings"] = {
        "network": "raw",
        "security": "reality",
        "realitySettings": {
            "serverName": sni,
            "fingerprint": "chrome",
            "publicKey": public_key,
            "shortId": short_id,
            "spiderX": "/"
        }
    }
    return outbound

def xrb_make_vless_xhttp_outbound(xray_inbound, xray_client, client_index):
    port = xray_inbound["port"]
    sni = xray_inbound["streamSettings"]["realitySettings"]["serverNames"][0]
    private_key = xray_inbound["streamSettings"]["realitySettings"]["privateKey"]
    xhttp_settings = xray_inbound["streamSettings"].get("xhttpSettings", {})

    # Xray developers think it's a GOOD and FUNNY idea to change the way
    # stuff is outputted per major release. So say, for version 26.2.6 it's
    # just "Password: <key>" but for 26.3.27 it's "Password (PublicKey): <key>"
    # ⠉⠉⠉⣿⡿⠿⠛⠋⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⣻⣩⣉⠉⠉
    # ⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⢀⣀⣀⣀⣀⣀⣀⡀⠄⠄⠉⠉⠄⠄⠄
    # ⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⣠⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣤⠄⠄⠄⠄
    # ⠄⠄⠄⠄⠄⠄⠄⠄⠄⢤⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠄⠄⠄
    # ⡄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠉⠄⠉⠉⠉⣋⠉⠉⠉⠉⠉⠉⠉⠉⠙⠛⢷⡀⠄⠄
    # ⣿⡄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠠⣾⣿⣷⣄⣀⣀⣀⣠⣄⣢⣤⣤⣾⣿⡀⠄
    # ⣿⠃⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⣹⣿⣿⡿⠿⣿⣿⣿⣿⣿⣿⣿⣿⢟⢁⣠
    # ⣿⣿⣄⣀⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠉⠉⣉⣉⣰⣿⣿⣿⣿⣷⣥⡀⠉⢁⡥⠈
    # ⣿⣿⣿⢹⣇⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠒⠛⠛⠋⠉⠉⠛⢻⣿⣿⣷⢀⡭⣤⠄
    # ⣿⣿⣿⡼⣿⠷⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⢀⣀⣠⣿⣟⢷⢾⣊⠄⠄
    # ⠉⠉⠁⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠈⣈⣉⣭⣽⡿⠟⢉⢴⣿⡇⣺⣿⣷
    # ⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠁⠐⢊⣡⣴⣾⣥⣿⣿⣿

    xray_x25519_raw = subprocess.check_output(["xray", "x25519", "-i", private_key], text=True).rstrip().strip()
    xray_x25519_lines = xray_x25519_raw.split("\n")
    xray_x25519_password_line = next(line for line in xray_x25519_lines if "Password" in line or "PublicKey" in line)
    assert xray_x25519_password_line, "Failed to get public key from xray x25519 output"
    public_key = xray_x25519_password_line.split(":", 1)[1].strip()

    short_id = xray_inbound["streamSettings"]["realitySettings"]["shortIds"][client_index]

    outbound = {}
    outbound["tag"] = xray_client.get("email", f"client{client_index}")
    outbound["protocol"] = "vless"
    outbound["settings"] = {
        "vnext": [{
            "address": SERVER_ADDRESS,
            "port": port,
            "users": [{
                "id": xray_client["id"],
                "encryption": "none"
            }]
        }]
    }
    outbound["streamSettings"] = {
        "network": "xhttp",
        "security": "reality",
        "realitySettings": {
            "serverName": sni,
            "fingerprint": "chrome",
            "publicKey": public_key,
            "shortId": short_id
        },
        "xhttpSettings": xhttp_settings
    }
    return outbound

def xrb_make_client_outbound(xray_inbound, xray_client, client_index):
    if xray_inbound["protocol"] == "vless":
        network = xray_inbound.get("streamSettings", {}).get("network", "raw")
        if network == "xhttp":
            return xrb_make_vless_xhttp_outbound(xray_inbound, xray_client, client_index)
        return xrb_make_vless_outbound(xray_inbound, xray_client, client_index)
    return None

def xrb_dump_urls(screen, xray_inbound):
    if 0 == len(xray_inbound["settings"]["clients"]):
        msgbox = UU_MessageBox(screen, "No clients to dump URLs for")
        msgbox.show()
        return

    menu = UU_InputMenu(screen, "Enter file path to dump URLs", f"{xray_inbound['tag']}_urldump.csv")
    path = menu.get()

    with open(path, "w") as url_file:
        url_file.write("client_index,email,url\n")
        for i, client in enumerate(xray_inbound["settings"]["clients"]):
            url = xrb_make_client_url(xray_inbound, client, i)
            url_file.write(f"{i},{client['email']},{url}\n")
    
    msgbox = UU_MessageBox(screen, f"URLs dumped to {path}")
    msgbox.show()


def xrb_dump_outbounds(screen, xray_inbound):
    if 0 == len(xray_inbound["settings"]["clients"]):
        UU_MessageBox(screen, "No clients to dump outbounds for").show()
        return

    clients = xray_inbound["settings"]["clients"]
    if len(clients) == 1:
        default_path = f"{xray_inbound['tag']}_outbound.json"
    else:
        default_path = f"{xray_inbound['tag']}_outbounds.json.list"

    path = UU_InputMenu(screen, "Enter file path to dump outbounds", default_path).get()

    with open(path, "w") as out_file:
        if len(clients) == 1:
            outbound = xrb_make_client_outbound(xray_inbound, clients[0], 0)
            out_file.write(json.dumps(outbound, ensure_ascii=False))
        else:
            for i, client in enumerate(clients):
                outbound = xrb_make_client_outbound(xray_inbound, client, i)
                if outbound:
                    out_file.write(json.dumps(outbound, ensure_ascii=False) + "\n")

    UU_MessageBox(screen, f"Outbounds dumped to {path}").show()

def xrb_dump_all_outbounds(screen, xray_config):
    if 0 == len(xray_config["inbounds"]):
        UU_MessageBox(screen, "No inbounds to dump outbounds for").show()
        return

    path = UU_InputMenu(screen, "Enter file path to dump all outbounds", "xrboot_outbounds.json.list").get()

    with open(path, "w") as out_file:
        for xray_inbound in xray_config["inbounds"]:
            for i, client in enumerate(xray_inbound["settings"]["clients"]):
                outbound = xrb_make_client_outbound(xray_inbound, client, i)
                if outbound:
                    out_file.write(json.dumps(outbound, ensure_ascii=False) + "\n")

    UU_MessageBox(screen, f"All outbounds dumped to {path}").show()

def xrb_manage_clients(screen, xray_inbound):
    while True:
        menu = UU_ChoiceMenu(screen, "Manage clients")

        for i, client in enumerate(xray_inbound["settings"]["clients"]):
            menu.add_choice(f"[{i}] {client['email']}")

        menu.add_separator()
        menu.add_choice("Make URL dump")
        menu.add_choice("Make outbound dump")
        menu.add_separator()
        menu.add_choice("Create New", is_default=(0 == len(xray_inbound["settings"]["clients"])))
        menu.add_separator()
        menu.add_choice("Back")

        choice = menu.get()

        if choice == menu.size() - 6: # Make URL dump
            xrb_dump_urls(screen, xray_inbound)
            continue

        if choice == menu.size() - 5: # Make outbound dump
            xrb_dump_outbounds(screen, xray_inbound)
            continue

        if choice == menu.size() - 3: # Create New
            xray_inbound = xrb_create_client(screen, xray_inbound)
            continue

        if choice == menu.size() - 1: # Back
            break

        xray_client = xrb_edit_client(screen, xray_inbound, xray_inbound["settings"]["clients"][choice], choice)

        if xray_client == None:
            if xray_inbound["protocol"] == "vless":
                xray_inbound["streamSettings"]["realitySettings"]["shortIds"].pop(choice)
            xray_inbound["settings"]["clients"].pop(choice)
        else:
            xray_inbound["settings"]["clients"][choice] = xray_client

    return xray_inbound

def xrb_edit_vless_sni(screen, xray_inbound):
    current_sni = xray_inbound["streamSettings"]["realitySettings"]["serverNames"][0]

    sni_menu = UU_ChoiceMenu(screen, "Select SNI")

    for i, sni in enumerate(VLESS_SNI_PREDEFS):
        sni_menu.add_choice(sni, is_default=(sni == current_sni))
    sni_menu.add_separator()
    sni_menu.add_choice("Custom", is_default=(current_sni not in VLESS_SNI_PREDEFS))

    snii = sni_menu.get()

    if snii == sni_menu.size() - 1: # Custom
        sni_input = UU_InputMenu(screen, "Enter SNI", current_sni)
        sni = sni_input.get()
    else:
        sni = sni_menu.choices[snii]

    xray_inbound["streamSettings"]["realitySettings"]["serverNames"] = [sni]
    xray_inbound["streamSettings"]["realitySettings"]["dest"] = f"{sni}:443"

    return xray_inbound

def xrb_edit_inbound_port(screen, xray_inbound):
    current_port = xray_inbound["port"]

    port_menu = UU_ChoiceMenu(screen, "Select port")

    for i, port in enumerate(PORT_PREDEFS):
        port_menu.add_choice(port, is_default=(current_port == port))
    port_menu.add_separator()
    port_menu.add_choice("Custom", is_default=(current_port not in PORT_PREDEFS))
    port_menu.add_choice("Random")

    porti = port_menu.get()

    if porti == port_menu.size() - 2: # Custom
        port_input = UU_InputMenu(screen, "Enter port", str(current_port))
        port = int(port_input.get())
    elif porti == port_menu.size() - 1: # Random
        port = random.randrange(1024, 5120)
    else:
        port = port_menu.choices[porti]

    xray_inbound["port"] = port

    return xray_inbound

def xrb_edit_inbound_tag(screen, xray_inbound):
    tag_input = UU_InputMenu(screen, "Enter inbound tag", xray_inbound["tag"])
    tag = tag_input.get()
    xray_inbound["tag"] = tag
    return xray_inbound

def xrb_manage_inbound(screen, xray_inbound):
    while True:
        menu = UU_ChoiceMenu(screen, f"Inbound: {xray_inbound['tag']}")
        menu.add_choice("Manage clients")
        menu.add_separator()
        menu.add_choice("Change tag")
        menu.add_choice("Change port")
        if xray_inbound["protocol"] == "vless":
            menu.add_choice("Change SNI")
        menu.add_separator()
        menu.add_choice("Remove inbound")
        menu.add_separator()
        menu.add_choice("Back")

        choice = menu.get()

        if choice == 0: # Manage clients
            xray_inbound = xrb_manage_clients(screen, xray_inbound)
            continue

        if choice == 2: # Change tag
            xray_inbound = xrb_edit_inbound_tag(screen, xray_inbound)
            continue

        if choice == 3: # Change port
            xray_inbound = xrb_edit_inbound_port(screen, xray_inbound)
            continue

        if xray_inbound["protocol"] == "vless" and choice == 4: # Change SNI
            xray_inbound = xrb_edit_vless_sni(screen, xray_inbound)
            continue

        if choice == menu.size() - 3: # Remove inbound
            if UU_YesNoBox(screen, "Are you sure you want to remove this inbound?", default_yes=False).get():
                return None
            continue

        if choice == menu.size() - 1: # Back
            break

    return xray_inbound

def xrb_make_default_inbound_tag(screen, xray_config, protocol):
    index = 1
    for i, inbound in enumerate(xray_config["inbounds"]):
        if protocol == inbound["protocol"]:
            index += 1
    return f"{protocol}{index}"

def xrb_create_inbound_vless_raw(screen, xray_config):
    tag_input = UU_InputMenu(screen, "Enter inbound tag", xrb_make_default_inbound_tag(screen, xray_config, "vless"))
    tag = tag_input.get()

    port_menu = UU_ChoiceMenu(screen, "Select port")

    for i, port in enumerate(PORT_PREDEFS):
        port_menu.add_choice(port, is_default=(i == 0))
    port_menu.add_separator()
    port_menu.add_choice("Custom")
    port_menu.add_choice("Random")

    porti = port_menu.get()

    if porti == port_menu.size() - 2: # Custom
        port_input = UU_InputMenu(screen, "Enter port", str(random.randrange(1024, 5120)))
        port = int(port_input.get())
    elif porti == port_menu.size() - 1: # Random
        port = random.randrange(1024, 5120)
    else:
        port = port_menu.choices[porti]

    sni_menu = UU_ChoiceMenu(screen, "Select SNI")

    for i, sni in enumerate(VLESS_SNI_PREDEFS):
        sni_menu.add_choice(sni, is_default=(i == 0))
    sni_menu.add_separator()
    sni_menu.add_choice("Custom")

    snii = sni_menu.get()

    if snii == sni_menu.size() - 1: # Custom
        sni_input = UU_InputMenu(screen, "Enter SNI")
        sni = sni_input.get()
    else:
        sni = sni_menu.choices[snii]

    inbound = {}

    # Setup inbound
    inbound["tag"] = tag
    inbound["port"] = port
    inbound["protocol"] = "vless"

    # Setup clients
    inbound["settings"] = {}
    inbound["settings"]["clients"] = []

    # Setup VLESS-specific options
    inbound["settings"]["decryption"] = "none"

    # Setup sniffing
    inbound["sniffing"] = {}
    inbound["sniffing"]["enabled"] = True
    inbound["sniffing"]["destOverride"] = ["http", "tls", "quic", "fakedns"]

    # Setup stream settings
    inbound["streamSettings"] = {}
    inbound["streamSettings"]["network"] = "raw"
    inbound["streamSettings"]["security"] = "reality"

    private_key = re.search(r"PrivateKey:\s*(.+)", subprocess.check_output(["xray", "x25519"], text=True)).group(1).rstrip().strip()

    # Setup reality settings
    inbound["streamSettings"]["realitySettings"] = {}
    inbound["streamSettings"]["realitySettings"]["minClientVer"] = ""
    inbound["streamSettings"]["realitySettings"]["maxClientVer"] = ""
    inbound["streamSettings"]["realitySettings"]["maxTimeDiff"] = 0
    inbound["streamSettings"]["realitySettings"]["show"] = False
    inbound["streamSettings"]["realitySettings"]["dest"] = f"{sni}:443"
    inbound["streamSettings"]["realitySettings"]["privateKey"] = private_key
    inbound["streamSettings"]["realitySettings"]["serverNames"] = [sni]
    inbound["streamSettings"]["realitySettings"]["shortIds"] = []

    xray_config["inbounds"].append(inbound)

    return xray_config

def xrb_create_inbound_vless_xhttp(screen, xray_config):
    tag_input = UU_InputMenu(screen, "Enter inbound tag", xrb_make_default_inbound_tag(screen, xray_config, "vless"))
    tag = tag_input.get()

    port_menu = UU_ChoiceMenu(screen, "Select port")

    for i, port in enumerate(PORT_PREDEFS):
        port_menu.add_choice(port, is_default=(i == 0))
    port_menu.add_separator()
    port_menu.add_choice("Custom")
    port_menu.add_choice("Random")

    porti = port_menu.get()

    if porti == port_menu.size() - 2: # Custom
        port_input = UU_InputMenu(screen, "Enter port", str(random.randrange(1024, 5120)))
        port = int(port_input.get())
    elif porti == port_menu.size() - 1: # Random
        port = random.randrange(1024, 5120)
    else:
        port = port_menu.choices[porti]

    sni_menu = UU_ChoiceMenu(screen, "Select SNI")

    for i, sni in enumerate(VLESS_SNI_PREDEFS):
        sni_menu.add_choice(sni, is_default=(i == 0))
    sni_menu.add_separator()
    sni_menu.add_choice("Custom")

    snii = sni_menu.get()

    if snii == sni_menu.size() - 1: # Custom
        sni_input = UU_InputMenu(screen, "Enter SNI")
        sni = sni_input.get()
    else:
        sni = sni_menu.choices[snii]

    path = UU_InputMenu(screen, "Enter xhttp path", "/api/v1/data").get()

    inbound = {}

    # Setup inbound
    inbound["tag"] = tag
    inbound["port"] = port
    inbound["protocol"] = "vless"

    # Setup clients
    inbound["settings"] = {}
    inbound["settings"]["clients"] = []

    # Setup VLESS-specific options
    inbound["settings"]["decryption"] = "none"

    # Setup sniffing
    inbound["sniffing"] = {}
    inbound["sniffing"]["enabled"] = True
    inbound["sniffing"]["destOverride"] = ["http", "tls", "quic"]

    # Setup stream settings
    inbound["streamSettings"] = {}
    inbound["streamSettings"]["network"] = "xhttp"
    inbound["streamSettings"]["security"] = "reality"

    private_key = re.search(r"PrivateKey:\s*(.+)", subprocess.check_output(["xray", "x25519"], text=True)).group(1).rstrip().strip()

    # Setup reality settings
    inbound["streamSettings"]["realitySettings"] = {}
    inbound["streamSettings"]["realitySettings"]["show"] = False
    inbound["streamSettings"]["realitySettings"]["dest"] = f"{sni}:443"
    inbound["streamSettings"]["realitySettings"]["xver"] = 0
    inbound["streamSettings"]["realitySettings"]["serverNames"] = [sni]
    inbound["streamSettings"]["realitySettings"]["privateKey"] = private_key
    inbound["streamSettings"]["realitySettings"]["shortIds"] = []

    # Setup xhttp settings
    inbound["streamSettings"]["xhttpSettings"] = {}
    inbound["streamSettings"]["xhttpSettings"]["path"] = path
    inbound["streamSettings"]["xhttpSettings"]["mode"] = "auto"
    inbound["streamSettings"]["xhttpSettings"]["extra"] = {"xPaddingBytes": "100-1000"}

    xray_config["inbounds"].append(inbound)

    return xray_config

def xrb_auto_setup(screen, xray_config):
    preset_menu = UU_ChoiceMenu(screen, "Select preset for auto-setup")
    preset_menu.add_choice("VLESS-RAW", is_default=True)
    preset_menu.add_choice("VLESS-XHTTP")
    preset = preset_menu.get()

    xhttp_path = "/api/v1/data"
    if preset == 1: # VLESS-XHTTP
        xhttp_path = UU_InputMenu(screen, "Enter xhttp path", "/api/v1/data").get()

    created = 0

    for sni in VLESS_SNI_PREDEFS:
        for port in [443, random.randrange(1024, 5120)]:
            sni_slug = sni.replace(".", "_")
            tag = f"auto_{sni_slug}_{port}"

            private_key = re.search(r"PrivateKey:\s*(.+)", subprocess.check_output(["xray", "x25519"], text=True)).group(1).rstrip().strip()
            short_id = subprocess.check_output(["openssl", "rand", "-hex", "8"], text=True).rstrip()
            client_uuid = subprocess.check_output(["xray", "uuid"], text=True).rstrip()

            client = {"id": client_uuid, "email": f"auto@{tag}"}
            if preset == 0: # VLESS-RAW
                client["flow"] = "xtls-rprx-vision"

            reality = {
                "show": False,
                "dest": f"{sni}:443",
                "serverNames": [sni],
                "privateKey": private_key,
                "shortIds": [short_id],
            }

            inbound = {}
            inbound["tag"] = tag
            inbound["port"] = port
            inbound["protocol"] = "vless"
            inbound["settings"] = {"clients": [client], "decryption": "none"}
            inbound["streamSettings"] = {"security": "reality"}

            if preset == 0: # VLESS-RAW
                reality["minClientVer"] = ""
                reality["maxClientVer"] = ""
                reality["maxTimeDiff"] = 0
                inbound["sniffing"] = {"enabled": True, "destOverride": ["http", "tls", "quic", "fakedns"]}
                inbound["streamSettings"]["network"] = "raw"
            else: # VLESS-XHTTP
                reality["xver"] = 0
                inbound["sniffing"] = {"enabled": True, "destOverride": ["http", "tls", "quic"]}
                inbound["streamSettings"]["network"] = "xhttp"
                inbound["streamSettings"]["xhttpSettings"] = {
                    "path": xhttp_path,
                    "mode": "auto",
                    "extra": {"xPaddingBytes": "100-1000"},
                }

            inbound["streamSettings"]["realitySettings"] = reality
            xray_config["inbounds"].append(inbound)
            created += 1

    UU_MessageBox(screen, f"Auto-setup complete: {created} inbounds created").show()
    return xray_config

def xrb_create_inbound(screen, xray_config):
    protocol_menu = UU_ChoiceMenu(screen, "Select inbound template")
    protocol_menu.add_choice("VLESS-RAW", is_default=True)
    protocol_menu.add_choice("VLESS-XHTTP")

    choice = protocol_menu.get()

    if choice == 0: # VLESS-RAW
        xray_config = xrb_create_inbound_vless_raw(screen, xray_config)
        return xray_config

    if choice == 1: # VLESS-XHTTP
        xray_config = xrb_create_inbound_vless_xhttp(screen, xray_config)
        return xray_config

    return xray_config

def xrb_dump_all_urls(screen, xray_config):
    if 0 == len(xray_config["inbounds"]):
        msgbox = UU_MessageBox(screen, "No inbounds to dump URLs for")
        msgbox.show()
        return

    menu = UU_InputMenu(screen, "Enter file path to dump all URLs", "xrboot_urldump.csv")
    path = menu.get()

    with open(path, "w") as url_file:
        url_file.write("inbound_index,inbound_tag,client_index,email,url\n")
        for j, xray_inbound in enumerate(xray_config["inbounds"]):
            for i, client in enumerate(xray_inbound["settings"]["clients"]):
                url = xrb_make_client_url(xray_inbound, client, i)
                url_file.write(f"{j},{xray_inbound['tag']},{i},{client['email']},{url}\n")

    msgbox = UU_MessageBox(screen, f"All URLs dumped to {path}")
    msgbox.show()

def xrb_manage_inbounds(screen, xray_config):
    while True:
        menu = UU_ChoiceMenu(screen, "Manage inbounds")

        for i, inbound in enumerate(xray_config["inbounds"]):
            menu.add_choice(f"[{i}] {inbound['tag']}")

        menu.add_separator()
        menu.add_choice("Make URL dump")
        menu.add_choice("Make outbound dump")
        menu.add_separator()
        menu.add_choice("Create New", is_default=(0 == len(xray_config["inbounds"])))
        menu.add_separator()
        menu.add_choice("Back")

        choice = menu.get()

        if choice == menu.size() - 6: # Make URL dump
            xrb_dump_all_urls(screen, xray_config)
            continue

        if choice == menu.size() - 5: # Make outbound dump
            xrb_dump_all_outbounds(screen, xray_config)
            continue

        if choice == menu.size() - 3: # Create New
            xray_config = xrb_create_inbound(screen, xray_config)
            continue

        if choice == menu.size() - 1: # Back
            break

        xray_inbound = xrb_manage_inbound(screen, xray_config["inbounds"][choice])

        if xray_inbound == None:
            xray_config["inbounds"].pop(choice)
        else:
            xray_config["inbounds"][choice] = xray_inbound

    return xray_config

def xrb_create_config(screen):
    xray_config = {}

    log_menu = UU_ChoiceMenu(screen, "Select log level for new config")
    log_menu.add_choice("debug")
    log_menu.add_choice("info")
    log_menu.add_choice("warning", is_default=True)
    log_menu.add_choice("error")
    log_menu.add_choice("none")

    logleveli = log_menu.get()
    loglevel = log_menu.choices[logleveli]

    # Setup loglevel
    xray_config["log"] = {}
    xray_config["log"]["loglevel"] = loglevel

    freedom_outbound = {}
    freedom_outbound["protocol"] = "freedom"
    freedom_outbound["tag"] = "direct"

    blackhole_outbound = {}
    blackhole_outbound["protocol"] = "blackhole"
    blackhole_outbound["tag"] = "block"

    # Setup outbounds
    xray_config["outbounds"] = []
    xray_config["outbounds"].append(freedom_outbound)
    xray_config["outbounds"].append(blackhole_outbound)

    # Setup routing
    xray_config["routing"] = {}
    xray_config["routing"]["rules"] = []
    xray_config["routing"]["domainStrategy"] = "AsIs"

    # Define empty inbounds
    xray_config["inbounds"] = []

    return xray_config

def xrb_edit_log_level(screen, xray_config):
    current_level = xray_config.get("log", {}).get("loglevel", "warning")

    loglevel_menu = UU_ChoiceMenu(screen, "Select log level")
    loglevel_menu.add_choice("debug", is_default=(current_level == "debug"))
    loglevel_menu.add_choice("info", is_default=(current_level == "info"))
    loglevel_menu.add_choice("warning", is_default=(current_level == "warning"))
    loglevel_menu.add_choice("error", is_default=(current_level == "error"))
    loglevel_menu.add_choice("none", is_default=(current_level == "none"))

    selected_level = loglevel_menu.choices[loglevel_menu.get()]

    if "log" not in xray_config:
        xray_config["log"] = {}
    xray_config["log"]["loglevel"] = selected_level

    return xray_config

def make_version_integer(version_string):
    parts = version_string.split(".")
    assert len(parts) == 3, "Version string should be in format X.Y.Z"

    major = int(parts[0])
    minor = int(parts[1])
    patch = int(parts[2])

    return 10000 * major + 100 * minor + patch

def xrb_main(screen):
    if os.name != "nt" and os.geteuid() != 0:
        UU_MessageBox(screen, "This script must be run as root").show()
        return 1

    REQUIRED_BINARIES = [ "xray", "openssl", "systemctl", "sleep" ]

    for binary in REQUIRED_BINARIES:
        if not shutil.which(binary):
            UU_MessageBox(screen, f"Required utility {binary} is not found in PATH").show()
            return 1

    # Get xray-core version
    xray_version = subprocess.check_output(["xray", "version"], text=True)
    xray_version = re.search(r"Xray\s+(\d+\.\d+\.\d+)", xray_version).group(1)
    xray_version = make_version_integer(xray_version.rstrip().strip())
    required_version = make_version_integer(MIN_XRAY_VERSION)

    if xray_version < required_version:
        UU_MessageBox(screen, f"Xray version {xray_version} is too old, please update to at least {MIN_XRAY_VERSION}").show()
        return 1

    xray_config_name = UU_InputMenu(screen, "XRay configuration name", "xrboot").get()
    xray_config_path = UU_InputMenu(screen, "XRay configuration file", f"/usr/local/etc/xray/{xray_config_name}.json").get()

    try:
        with open(xray_config_path, "r") as json_file:
            xray_config = json.load(json_file)
            if "inbounds" not in xray_config:
                raise ValueError("Invalid config: missing 'inbounds' key")
            if "outbounds" not in xray_config:
                raise ValueError("Invalid config: missing 'outbounds' key")
            if "routing" not in xray_config:
                raise ValueError("Invalid config: missing 'routing' key")
            if "log" not in xray_config:
                raise ValueError("Invalid config: missing 'log' key")
            if "loglevel" not in xray_config["log"]:
                raise ValueError("Invalid config: missing 'log.loglevel' key")
            if 0 == len(xray_config["outbounds"]):
                raise ValueError("Invalid config: no outbounds defined")
            if "rules" not in xray_config["routing"]:
                raise ValueError("Invalid config: missing 'routing.rules' key")
    except:
        if not UU_YesNoBox(screen, f"File {xray_config_path} is missing or corrupted. Create?").get():
            return 1
        xray_config = xrb_create_config(screen)

    while True:
        menu = UU_ChoiceMenu(screen, f"xrayboot.py v{VERSION} by untodesu")
        menu.add_choice("Manage Inbounds")
        menu.add_choice("Auto-setup")
        menu.add_separator()
        menu.add_choice("Edit log level")
        menu.add_separator()
        menu.add_choice("Save & Exit")
        menu.add_choice("Exit")

        choice = menu.get()

        if choice == 0: # Manage Inbounds
            xray_config = xrb_manage_inbounds(screen, xray_config)
            continue

        if choice == 1: # Auto-setup
            xray_config = xrb_auto_setup(screen, xray_config)
            continue

        if choice == 3: # Edit log level
            xray_config = xrb_edit_log_level(screen, xray_config)
            continue

        if choice == 5: # Save & Exit
            UU_MessageBox(screen, f"The script will save the config to {xray_config_path}").show()
            break

        if choice == 6: # Exit
            if UU_YesNoBox(screen, "Are you sure you want to exit without saving?", default_yes=False).get():
                return 0
            continue

    with open(xray_config_path, "w") as json_file:
        json.dump(xray_config, json_file, indent=2)

    if os.name == "nt":
        UU_MessageBox(screen, "Running under Windows NT, not calling systemctl").show()
    elif UU_YesNoBox(screen, f"Restart service xray@{xray_config_name}?").get():
        curses.endwin()
        subprocess.run(["/bin/sleep", "2.0"])
        subprocess.run(["/usr/bin/systemctl", "enable", f"xray@{xray_config_name}"])
        subprocess.run(["/usr/bin/systemctl", "restart", f"xray@{xray_config_name}"])
        subprocess.run(["/usr/bin/systemctl", "status", f"xray@{xray_config_name}", "--no-pager"])
    return 0

if __name__ == "__main__":
    screen = curses.initscr()
    if os.name == "nt":
        screen.nodelay(True)
    screen.keypad(True)
    try:
        retval = xrb_main(screen)
    finally:
        curses.endwin()
    sys.exit(retval)
