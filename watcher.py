"""UIUC seat watcher: checks Course Explorer for open seats and sends a WhatsApp alert.

Reads classes.md, checks each section's enrollment status, and alerts once when a
section changes from closed to open. State is kept in state.json so you don't get
spammed every run.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parent
CLASSES_FILE = ROOT / "classes.md"
STATE_FILE = ROOT / "state.json"
API = "https://courses.illinois.edu/cisapp/explorer/schedule"
BANNER = "https://banner.apps.uillinois.edu/StudentRegistrationSSB/ssb/classRegistration/classRegistration"
HEADERS = {"User-Agent": "uiuc-seat-watcher/1.0"}


def parse_classes():
    text = CLASSES_FILE.read_text()
    m = re.search(r"^Term:\s*(\d{4})\s+(spring|summer|fall|winter)", text, re.I | re.M)
    if not m:
        sys.exit("classes.md needs a line like 'Term: 2027 spring'")
    year, season = m.group(1), m.group(2).lower()

    watching = text.split("## Watching", 1)[-1]
    classes = []
    for line in watching.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line.startswith(("-", "*")):
            continue
        parts = line.lstrip("-* ").replace("`", "").upper().split()
        if len(parts) >= 2 and parts[0].isalpha() and parts[1].isdigit():
            crn = parts[2] if len(parts) >= 3 and parts[2].isdigit() else None
            classes.append((parts[0], parts[1], crn))
    return year, season, classes


def strip_ns(tag):
    return tag.rsplit("}", 1)[-1]


def fetch_xml(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return ET.fromstring(r.read())


def find_text(el, name):
    for child in el.iter():
        if strip_ns(child.tag) == name and child.text:
            return child.text.strip()
    return None


def get_sections(year, season, subj, num):
    """Return {crn: (status, label)} for every section of a course."""
    root = fetch_xml(f"{API}/{year}/{season}/{subj}/{num}.xml?mode=detail")
    out = {}
    for el in root.iter():
        if strip_ns(el.tag) in ("detailedSection", "section") and el.get("id"):
            status = find_text(el, "enrollmentStatus") or "UNKNOWN"
            label = find_text(el, "sectionNumber") or el.get("id")
            out[el.get("id")] = (status, label)
    return out


def is_open(status):
    s = status.lower()
    return s.startswith("open") or s == "crosslistopen"


def send_whatsapp(msg):
    phone, key = os.environ.get("WHATSAPP_PHONE"), os.environ.get("CALLMEBOT_APIKEY")
    if not phone or not key:
        print("No WhatsApp secrets set; would have sent:\n" + msg)
        return
    q = urllib.parse.urlencode({"phone": phone, "text": msg, "apikey": key})
    req = urllib.request.Request(f"https://api.callmebot.com/whatsapp.php?{q}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        print("WhatsApp:", r.status)


def main():
    if os.environ.get("TEST_MESSAGE") == "true":
        send_whatsapp("Seat watcher test: notifications are working.")
        return

    year, season, classes = parse_classes()
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    new_state, alerts = {}, []

    for subj, num, crn in classes:
        name = f"{subj} {num}"
        try:
            sections = get_sections(year, season, subj, num)
        except Exception as e:
            print(f"{name}: lookup failed ({e})")
            # keep old state so a temporary error doesn't trigger a duplicate alert
            new_state.update({k: v for k, v in state.items() if k.startswith(f"{name}|")})
            continue
        if crn and crn not in sections:
            print(f"{name}: CRN {crn} not found (check classes.md)")
            continue
        for c, (status, label) in sections.items():
            if crn and c != crn:
                continue
            key = f"{name}|{c}"
            print(f"{name} sec {label} (CRN {c}): {status}")
            new_state[key] = status
            if is_open(status) and not is_open(state.get(key, "Closed")):
                alerts.append(f"{name} sec {label} (CRN {c}) is {status}")

    if alerts:
        send_whatsapp("Seat open!\n" + "\n".join(alerts) + f"\nRegister: {BANNER}")

    STATE_FILE.write_text(json.dumps(new_state, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
