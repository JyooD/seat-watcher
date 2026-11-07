# UIUC Seat Watcher

Checks UIUC Course Explorer every ~10 minutes and sends you a WhatsApp message
when a full section opens up. You still register yourself in Banner.

## Setup (one time, ~10 min)

1. **Get a WhatsApp API key (CallMeBot, free)**
   - Add **+34 644 66 32 62** to your phone contacts.
   - Send it this WhatsApp message: `I allow callmebot to send me messages`
   - It replies with your API key.
2. **Create a GitHub repo** (private is fine) and push this folder to it.
3. **Add secrets**: repo → Settings → Secrets and variables → Actions → New repository secret
   - `WHATSAPP_PHONE`: your number with country code, e.g. `+12175551234`
   - `CALLMEBOT_APIKEY`: the key from step 1
4. **Test it**: repo → Actions → Seat watcher → Run workflow → check "Send a test
   WhatsApp message" → Run. You should get a message within a minute.

## Adding classes

Edit `classes.md` (you can do it right on github.com) and add lines under `## Watching`:

```
- ECON 414 12345
- CS 421
```

Commit, and the next run picks it up.

## Notes

- You get one alert when a section goes from closed to open, not one every run.
  If it closes and reopens, you'll be alerted again.
- Course Explorer can lag Banner by a bit, so move fast when you get the alert.
- "Open (Restricted)" also triggers an alert. Check whether the restriction applies to you.
- GitHub pauses scheduled workflows in repos with no activity for 60 days. The state
  commits usually keep it alive, but re-enable it under Actions if it stops.
