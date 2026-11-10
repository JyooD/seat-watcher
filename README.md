# UIUC Seat Watcher

A tiny bot that watches UIUC [Course Explorer](https://courses.illinois.edu/)
for you and sends a push notification to your phone (via
[ntfy](https://ntfy.sh)) the moment a full section opens up, so you
don't have to keep refreshing Banner during registration week. It runs for
free on GitHub Actions, on a schedule, with no server to maintain.

You still have to register yourself — this only tells you *when* to.

## How it works

- `watcher.py` reads the courses you're watching from `classes.md`, reads
  each course's page on Course Explorer, and compares the current enrollment
  status against the last known status, which it keeps in `state.json`.
- Whenever a section's status changes, `notify.py` sends you one push
  notification (tap it to open registration). A section opening up is sent as
  **urgent**; other changes (closing again, becoming restricted) are normal
  notifications. Nothing is sent while a status stays the same.
- `.github/workflows/watch.yml` is a GitHub Actions workflow that runs
  `watcher.py` every 15 minutes, passing your ntfy topic in as a secret, and commits the updated `state.json` back to
  the repo so state persists between runs.

## Setup (one time, ~5 min)

1. **Install ntfy (free, no account)**
   - Install the **ntfy** app from the App Store or Google Play and allow
     notifications.
   - Tap **+** / *Subscribe to topic* and make up a long random topic name,
     e.g. `jae-seats-8f3k2q`. Anyone who knows the name can read it, so don't
     use something guessable.
2. **Push this folder to a GitHub repo** (private is fine).
3. **Add one repository secret**: repo → Settings → Secrets and variables →
   Actions → New repository secret
   - `NTFY_TOPIC` — the topic name from step 1 (just the name, no URL)
4. **Test it**: repo → Actions → Seat watcher → Run workflow → check "Send a
   test notification" → Run. Your phone should buzz within a few seconds.
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

Commit the change, and the next run (within ~15 min) picks it up.
Delete a line once you're registered for it so it stops checking.

## Notes

- You get one alert per status change, not one every run. If a seat opens,
  closes and reopens, you'll hear about each change.
- Course Explorer can lag Banner by a bit, so move fast when you get the
  alert — other people are watching too.
- "Open (Restricted)" also triggers an alert. Check whether the restriction
  (e.g. major, year) applies to you before rushing to register.
- GitHub pauses scheduled workflows in repos with no activity for 60 days.
  The state commits usually keep it alive, but re-enable it under the
  Actions tab if a run stops firing.

## Troubleshooting

- **No test notification arrives**: check that `NTFY_TOPIC` matches the topic
  you subscribed to in the app exactly (it's case-sensitive), and that
  notifications are allowed for ntfy in your phone's settings. On iPhone,
  turn off Focus/Do Not Disturb or allow ntfy through it.
- **Test locally**: `NTFY_TOPIC=your-topic python notify.py "hello"`.
- **Workflow run shows a lookup failed**: Course Explorer was likely
  temporarily down or slow; the watcher keeps last-known state so this
  won't cause a false alert.
- **CRN not found**: double-check the CRN in `classes.md` against the course
  catalog — it's specific to the term listed at the top of that file.

## Reliable 15-minute checks (cron-job.org)

GitHub's own schedule often runs only every few hours on small repos, so an
outside timer triggers the workflow instead. GitHub's schedule stays on as an
hourly-ish backup.

1. **Make a token**: GitHub → Settings → Developer settings → Fine-grained tokens →
   Generate new token.
   - Repository access: *Only select repositories* → `seat-watcher`
   - Permissions: **Actions → Read and write** (nothing else)
   - Expiration: past the end of registration (e.g. 90 days)
2. **Create the cron job** at https://cron-job.org (free account):
   - URL: `https://api.github.com/repos/JyooD/seat-watcher/actions/workflows/watch.yml/dispatches`
   - Schedule: every 15 minutes
   - Advanced → Request method: **POST**
   - Headers:
     - `Authorization: Bearer <your token>`
     - `Accept: application/vnd.github+json`
     - `X-GitHub-Api-Version: 2022-11-28`
   - Request body: `{"ref":"master"}`
   - Turn on cron-job.org's "notify me when execution fails" email.
3. Click **Test run**. It should return status **204**, and a new run should appear
   under Actions within a few seconds.

## Safeguards

- **Health check every 3 hours**: the first run in each 3-hour block (12am, 3am, 6am,
  9am, 12pm, 3pm, 6pm, 9pm Chicago time) sends a quiet notification with every section's
  status and how many checks ran in the last 3h (~12 expected).
  **No health check for 3+ hours = something is broken.** Check cron-job.org and Actions.
- **Problem alerts**: if a class can't be looked up, a CRN isn't found, or a status
  comes back UNKNOWN, the run turns red (GitHub emails you) and you get one phone
  warning per day.
- **Notification failures**: if ntfy can't be reached or rejects a message, the run
  turns red instead of passing silently.
- **Token expiry**: when the token expires, cron-job.org starts failing (it emails you)
  and checks slow to the GitHub backup rate. Make a new token and update the header.
