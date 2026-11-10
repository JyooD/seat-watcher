"""UIUC seat watcher: checks Course Explorer for open seats and sends a phone alert (ntfy).

Reads classes.md, checks each section's enrollment status, and alerts whenever a
section's status changes (urgent if it just opened). Every 3 hours it also sends a
health check listing every section's status. State is kept in state.json so you
only hear about changes, not the same status every run.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import notify

ROOT = Path(__file__).parent
CLASSES_FILE = ROOT / "classes.md"
STATE_FILE = ROOT / "state.json"
SCHEDULE = "https://courses.illinois.edu/schedule"
BANNER = "https://banner.apps.uillinois.edu/StudentRegistrationSSB/ssb/classRegistration/classRegistration"
HEADERS = {"User-Agent": "uiuc-seat-watcher/1.0"}
HEALTH_EVERY_HOURS = 3   # health check at 12am, 3am, 6am, ... Chicago time
CHECK_EVERY_MIN = 15     # how often cron-job.org triggers a run

# Matches each section row via its "add to favorites" link, which is the
# only place the CRN reliably appears next to the section's status icon.
ROW_RE = re.compile(r"/userredirect/favorite/\d+/\w+/[A-Z]+/\d+/(\d+)")
STATUS_RE = re.compile(r'aria-label="Section ([^"]+)"')
LABEL_RE = re.compile(r'type-col dt-body-left">\s*<div class="app-meeting">([^<]+)</div>')


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


def fetch_html(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def get_sections(year, season, subj, num):
    """Return {crn: (status, label)} for every section of a course.

    Course Explorer's XML API no longer reports enrollment status (every
    section just comes back "A" for active, open or not), so this scrapes
    the human-facing schedule page instead, which still shows a real
    Open/Closed/Open (Restricted) icon per section.
    """
    html = fetch_html(f"{SCHEDULE}/{year}/{season}/{subj}/{num}")
    out = {}
    for m in ROW_RE.finditer(html):
        crn = m.group(1)
        before = html[max(0, m.start() - 1500):m.start()]
        statuses = STATUS_RE.findall(before)
        status = statuses[-1] if statuses else "UNKNOWN"
        after = html[m.end():m.end() + 1500]
        label_m = LABEL_RE.search(after)
        label = label_m.group(1).strip() if label_m else crn
        out[crn] = (status, label)
    return out


def is_open(status):
    s = status.lower()
    return s.startswith("open") or s.startswith("crosslistopen")


def runs_since(hours):
    """Count this workflow's runs in the last `hours` hours (None if unavailable)."""
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return None
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"https://api.github.com/repos/{repo}/actions/workflows/watch.yml/runs?created=>={since}&per_page=1"
    req = urllib.request.Request(url, headers={**HEADERS, "Authorization": f"Bearer {token}",
                                               "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get("total_count")
    except Exception as e:
        print(f"Couldn't count runs: {e}")
        return None


def main():
    if os.environ.get("TEST_MESSAGE") == "true":
        notify.send("Seat watcher test: notifications are working.",
                    title="Seat watcher test", tags=["white_check_mark"])
        return

    year, season, classes = parse_classes()
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    new_state, opened, changed, problems, lines = {}, [], [], [], []

    for subj, num, crn in classes:
        name = f"{subj} {num}"
        try:
            sections = get_sections(year, season, subj, num)
        except Exception as e:
            print(f"{name}: lookup failed ({e})")
            problems.append(f"{name}: lookup failed")
            # keep old state so a temporary error doesn't look like a status change
            new_state.update({k: v for k, v in state.items() if k.startswith(f"{name}|")})
            continue
        if crn and crn not in sections:
            print(f"{name}: CRN {crn} not found (check classes.md)")
            problems.append(f"{name}: CRN {crn} not found")
            continue
        for c, (status, label) in sections.items():
            if crn and c != crn:
                continue
            key = f"{name}|{c}"
            print(f"{name} sec {label} (CRN {c}): {status}")
            lines.append(f"{name} {label} ({c}): {status}")
            old = state.get(key)
            if status == "UNKNOWN":
                problems.append(f"{name} CRN {c}: status UNKNOWN")
                if old:
                    new_state[key] = old
                continue
            new_state[key] = status
            if old is None:
                # Newly added to classes.md: only worth an alert if it's already open.
                if is_open(status):
                    opened.append(f"{name} sec {label} (CRN {c}): {status}")
            elif status != old:
                change = f"{name} sec {label} (CRN {c}): {old} -> {status}"
                (opened if is_open(status) and not is_open(old) else changed).append(change)

    # Alert on any status change. A section opening up is urgent; anything else
    # (closing again, becoming restricted, etc.) is a normal notification.
    # If sending fails, the run crashes before state is saved, so the next run retries.
    if opened:
        notify.send("\n".join(opened + changed) + "\nTap to open registration.",
                    title="Seat open!", priority="urgent", tags=["rotating_light"], click=BANNER)
    elif changed:
        notify.send("\n".join(changed), title="Seat status changed",
                    tags=["arrows_counterclockwise"], click=BANNER)

    # Health check: once per 3-hour block (12am, 3am, 6am, ... Chicago time),
    # listing every section's current status.
    now = datetime.now(ZoneInfo("America/Chicago"))
    today = now.date().isoformat()
    block = f"{today} {now.hour // HEALTH_EVERY_HOURS * HEALTH_EVERY_HOURS:02d}:00"
    last_health = state.get("_last_health")
    if last_health != block:
        runs = runs_since(HEALTH_EVERY_HOURS)
        msg = "\n".join(lines) or "(no sections checked)"
        if runs is not None:
            msg += (f"\nChecks in last {HEALTH_EVERY_HOURS}h: {runs} "
                    f"(expect ~{HEALTH_EVERY_HOURS * 60 // CHECK_EVERY_MIN})")
        if problems:
            msg += "\nProblems: " + "; ".join(problems)
        try:
            notify.send(msg, title="Seat watcher health check", priority="low", tags=["stethoscope"])
            last_health = block
        except Exception as e:
            problems.append(f"health check failed to send ({e})")
    if last_health:
        new_state["_last_health"] = last_health
    if state.get("_last_problem_alert"):
        new_state["_last_problem_alert"] = state["_last_problem_alert"]

    STATE_FILE.write_text(json.dumps(new_state, indent=2, sort_keys=True) + "\n")

    if problems:
        # Fail the run so GitHub emails you; one phone warning per day at most.
        if state.get("_last_problem_alert") != today:
            try:
                notify.send("\n".join(problems), title="Seat watcher problem",
                            priority="high", tags=["warning"])
            except Exception as e:
                print(f"Couldn't send problem alert: {e}")
            new_state["_last_problem_alert"] = today
            STATE_FILE.write_text(json.dumps(new_state, indent=2, sort_keys=True) + "\n")
        sys.exit("Problems: " + "; ".join(problems))


if __name__ == "__main__":
    main()
