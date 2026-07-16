#!/usr/bin/env python3
"""Pull recent nights from Oura and merge into data/sleep.json.

Merge key is the Oura session `id`. Not `day` — 126 days in 2025 alone hold more
than one session. Not `bedtime_start` — Oura re-scores nights after the fact and
that moves the timestamp. (Observed: 2022-04-02 is one consolidated 09:48→18:04
sleep in a 2023 CSV export and six separate fragments in today's API. Keyed on a
timestamp, that correction would settle in beside the stale row forever.)

Guards, because every failure in this genre is silent and still renders a pretty page:
  · zero records returned      -> abort, touch nothing
  · merge would lose records   -> abort loudly
  · never delete; only add or correct
"""
import json, os, sys, urllib.request, urllib.parse, datetime

ROOT   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SLIM   = os.path.join(ROOT, "data", "sleep.json")
WORKER = "https://circadian.rikkidelaine84.workers.dev"
# The Worker's gate is an Origin check. This is not a credential and not a trick:
# the Worker is restricted to the sleep endpoint, and everything it serves is
# already public at data/sleep.json. There is no secret behind it.
HDRS = {"Origin": "https://rikkikkir.github.io",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
LOOKBACK = 45   # generous: Oura back-fills and re-scores; re-reading is free, missing a night isn't


def fetch(start, end):
    out, tok = [], None
    while True:
        q = {"start_date": start, "end_date": end}
        if tok:
            q["next_token"] = tok
        req = urllib.request.Request(f"{WORKER}/v2/usercollection/sleep?" + urllib.parse.urlencode(q), headers=HDRS)
        j = json.load(urllib.request.urlopen(req, timeout=90))
        out += j.get("data", [])
        tok = j.get("next_token")
        if not tok:
            return out


def slim(r):
    s = datetime.datetime.fromisoformat(r["bedtime_start"])
    e = datetime.datetime.fromisoformat(r["bedtime_end"])
    return {
        "id": r["id"], "day": r["day"],
        "bedtime_start": r["bedtime_start"], "bedtime_end": r["bedtime_end"],
        "off": int(s.utcoffset().total_seconds() // 60),
        "dur": round((e - s).total_seconds() / 3600, 2),
        "tsd": r.get("total_sleep_duration"), "rem": r.get("rem_sleep_duration"),
        "deep": r.get("deep_sleep_duration"), "light": r.get("light_sleep_duration"),
        "hrv": r.get("average_hrv"), "hr": r.get("average_heart_rate"),
        "score": r.get("score"), "type": r.get("type"), "src": "api",
    }


existing = json.load(open(SLIM))
before = len(existing)
by_id = {r["id"]: r for r in existing}

today = datetime.date.today()
start = today - datetime.timedelta(days=LOOKBACK)
end   = today + datetime.timedelta(days=1)   # Oura files a night under the NEXT day
got = fetch(start.isoformat(), end.isoformat())

if not got:
    sys.exit(f"ABORT: Oura returned 0 sessions for {start}..{end}. Refusing to touch data/sleep.json.")

added = updated = 0
for r in got:
    if not (r.get("bedtime_start") and r.get("bedtime_end")):
        continue
    rec = slim(r)
    if rec["id"] not in by_id:
        by_id[rec["id"]] = rec; added += 1
    elif by_id[rec["id"]] != rec:
        by_id[rec["id"]] = rec; updated += 1      # a correction REPLACES its record

merged = sorted(by_id.values(), key=lambda r: r["bedtime_start"])

if len(merged) < before:
    sys.exit(f"ABORT: merge would drop records ({before} -> {len(merged)}). Refusing.")
if any(r.get("est") for r in merged):
    sys.exit("ABORT: an estimated record reached sleep.json. Measured data only.")

with open(SLIM, "w") as f:
    json.dump(merged, f, sort_keys=True, indent=1)   # sort_keys is load-bearing:
    f.write("\n")                                    # unstable key order costs 55x in git

print(f"fetched {len(got)} sessions over {LOOKBACK}d -> +{added} new, {updated} corrected, {len(merged)} total")
