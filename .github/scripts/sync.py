#!/usr/bin/env python3
"""Pull recent nights from Oura and add them to data/sleep.json — never changing a
record that is already there.

Merge key is the Oura session `id`. Not `day` — 126 days in 2025 alone hold more
than one session. Not `bedtime_start` — Oura re-scores nights after the fact and
that moves the timestamp. (Observed: 2022-04-02 is one consolidated 09:48→18:04
sleep in a 2023 CSV export and six separate fragments in today's API. Keyed on a
timestamp, that correction would settle in beside the stale row forever.)

APPEND-ONLY (Rikki, 2026-09-10: "ensure that data is only being added, not
overwriting or removing old data"). When Oura re-scores a night that is already in
sleep.json, the stored record stays exactly as it is and the new version is appended
to data/sleep_revisions.json as {captured_at, id, kind, record}. Readers that want
the current version apply those revisions (verify.py does).
.github/scripts/check_append_only.py enforces this before every commit.

Guards, because every failure in this genre is silent and still renders a pretty page:
  · zero records returned      -> abort, touch nothing
  · merge would lose records   -> abort loudly
  · never delete, never overwrite; only add
"""
import json, os, sys, urllib.request, urllib.parse, datetime

ROOT   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SLIM   = os.path.join(ROOT, "data", "sleep.json")
REV    = os.path.join(ROOT, "data", "sleep_revisions.json")
WORKER = "https://circadian.rikkidelaine84.workers.dev"
# The Worker's gate is an Origin check, not a credential. This job needs only the
# summary fields that are published here in data/sleep.json.
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


def main(fetcher=fetch):
    existing = json.load(open(SLIM))
    before = len(existing)
    by_id = {r["id"]: r for r in existing}
    revisions = json.load(open(REV)) if os.path.exists(REV) else []
    current = dict(by_id)
    for rv in revisions:
        if rv.get("kind") == "revision":        # "recovered" entries are history, never current
            current[rv["id"]] = rv["record"]

    today = datetime.date.today()
    start = today - datetime.timedelta(days=LOOKBACK)
    end   = today + datetime.timedelta(days=1)   # Oura files a night under the NEXT day
    got = fetcher(start.isoformat(), end.isoformat())

    if not got:
        sys.exit(f"ABORT: Oura returned 0 sessions for {start}..{end}. Refusing to touch data/sleep.json.")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    added = revised = 0
    for r in got:
        if not (r.get("bedtime_start") and r.get("bedtime_end")):
            continue
        rec = slim(r)
        if rec["id"] not in by_id:
            by_id[rec["id"]] = rec; current[rec["id"]] = rec; added += 1
        elif current[rec["id"]] != rec:
            revisions.append({"captured_at": now, "id": rec["id"], "kind": "revision", "record": rec})
            current[rec["id"]] = rec; revised += 1   # the stored record is NOT touched

    merged = sorted(by_id.values(), key=lambda r: r["bedtime_start"])

    if len(merged) < before:
        sys.exit(f"ABORT: merge would drop records ({before} -> {len(merged)}). Refusing.")
    if any(r.get("est") for r in merged):
        sys.exit("ABORT: an estimated record reached sleep.json. Measured data only.")

    with open(SLIM, "w") as f:
        json.dump(merged, f, sort_keys=True, indent=1)   # sort_keys is load-bearing:
        f.write("\n")                                    # unstable key order costs 55x in git
    if revised:
        with open(REV, "w") as f:
            json.dump(revisions, f, sort_keys=True, indent=1)
            f.write("\n")

    print(f"fetched {len(got)} sessions over {LOOKBACK}d -> +{added} new, {revised} revisions appended, "
          f"0 overwritten, {len(merged)} total")


if __name__ == "__main__":
    main()
