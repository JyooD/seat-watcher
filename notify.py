"""Send a push notification to your phone with ntfy (https://ntfy.sh).

Setup: install the ntfy app, subscribe to a long random topic name
(e.g. jae-seats-8f3k2q), and save that name as the NTFY_TOPIC repo secret.
Anyone who knows the topic name can read it, so keep it unguessable.

Run directly to send a test:  python notify.py "hello"
"""
import os
import sys
import urllib.request

NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")


def send(msg, title="Seat watcher", priority="default", tags=None, click=None):
    """Send one notification. Raises if it can't be delivered to ntfy.

    priority: "min", "low", "default", "high" or "urgent".
    tags: list of ntfy tag/emoji names, e.g. ["rotating_light"].
    click: URL opened when you tap the notification.
    """
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        raise RuntimeError("NTFY_TOPIC secret is not set")
    headers = {"User-Agent": "uiuc-seat-watcher/1.0", "Title": title, "Priority": priority}
    if tags:
        headers["Tags"] = ",".join(tags)
    if click:
        headers["Click"] = click
    req = urllib.request.Request(f"{NTFY_SERVER}/{topic}", data=msg.encode("utf-8"),
                                 headers=headers, method="POST")
    # urlopen raises HTTPError on any 4xx/5xx, so a failed send never passes silently.
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()
    print(f"Notification sent: {title}")


if __name__ == "__main__":
    send(" ".join(sys.argv[1:]) or "Seat watcher test: notifications are working.",
         title="Seat watcher test", tags=["white_check_mark"])
