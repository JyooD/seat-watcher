# UIUC Seat Watcher

A tiny bot that watches UIUC [Course Explorer](https://courses.illinois.edu/)
for you and pings your WhatsApp the moment a full section opens up, so you
don't have to keep refreshing Banner during registration week. It runs for
free on GitHub Actions, on a schedule, with no server to maintain.

You still have to register yourself — this only tells you *when* to.

## How it works

- `watcher.py` reads the courses you're watching from `classes.md`, queries
  the Course Explorer API for each one, and compares the current enrollment
  status against the last known status, which it keeps in `state.json`.
- If a section flips from closed to open, it sends you one WhatsApp message
  via [CallMeBot](https://www.callmebot.com/) and remembers that it already
  alerted you, so you don't get spammed every 10 minutes while the seat
  stays open.
- `.github/workflows/watch.yml` is a GitHub Actions workflow that runs
  `watcher.py` on a schedule (every ~10 minutes), passing your phone number
  and API key in as secrets, and commits the updated `state.json` back to
  the repo so state persists between runs.

## Setup (one time, ~10 min)

1. **Get a WhatsApp API key (CallMeBot, free)**
   - Add **+34 644 66 32 62** to your phone contacts.
   - Send it this WhatsApp message: `I allow callmebot to send me messages`
   - It replies with your API key. Save it somewhere.
2. **Push this folder to a GitHub repo** (private is fine).
3. **Add two repository secrets**: repo → Settings → Secrets and variables →
   Actions → New repository secret
   - `WHATSAPP_PHONE` — your number with country code, e.g. `+12175551234`
   - `CALLMEBOT_APIKEY` — the key from step 1
4. **Test it**: repo → Actions → Seat watcher → Run workflow → check "Send a
   test WhatsApp message" → Run. You should get a message within a minute.
   If nothing arrives, see Troubleshooting below.
5. **Add the classes you're watching** — see below — and commit.

## Adding classes

Edit `classes.md` (you can do it right on github.com) and add lines under
`## Watching`:

```
- ECON 414 12345
- CS 421
```

- `SUBJECT NUMBER CRN` watches one specific section (recommended — this is
  what shows up on your registration page).
- `SUBJECT NUMBER` with no CRN watches every section of that course and
  alerts on any of them.
- Anything after `#` on a line is a note and is ignored.

Commit the change, and the next scheduled run (within ~10 min) picks it up.
Delete a line once you're registered for it so it stops checking.

## Notes

- You get one alert when a section goes from closed to open, not one every
  run. If it closes and reopens, you'll be alerted again.
- Course Explorer can lag Banner by a bit, so move fast when you get the
  alert — other people are watching too.
- "Open (Restricted)" also triggers an alert. Check whether the restriction
  (e.g. major, year) applies to you before rushing to register.
- GitHub pauses scheduled workflows in repos with no activity for 60 days.
  The state commits usually keep it alive, but re-enable it under the
  Actions tab if a run stops firing.

## Troubleshooting

- **No test message arrives**: double check `WHATSAPP_PHONE` includes the
  `+` and country code, and that you messaged CallMeBot's number from the
  *same* WhatsApp account/number you put in the secret.
- **Workflow run shows a lookup failed**: Course Explorer was likely
  temporarily down or slow; the watcher keeps last-known state so this
  won't cause a false alert.
- **CRN not found**: double-check the CRN in `classes.md` against the course
  catalog — it's specific to the term listed at the top of that file.
