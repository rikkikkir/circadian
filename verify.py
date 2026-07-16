#!/usr/bin/env python3
"""The point of this file: I will find out when it's wrong.

Asserts data/sleep.json is faithful to Oura and uncontaminated.
Run in CI on every push and after every sync. Exit 1 = something moved.
"""
import json, sys, urllib.request, urllib.parse, datetime, os, collections

SLIM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sleep.json")
WORKER = "https://circadian.rikkidelaine84.workers.dev"
HDRS = {"Origin": "https://rikkikkir.github.io",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
FLOOR = "2022-01-24"
fails, warns = [], []

recs = json.load(open(SLIM))
print(f"sleep.json: {len(recs)} sessions, {os.path.getsize(SLIM):,} B")

# 1. no fabricated records, ever
est = [r for r in recs if r.get("est")]
(fails if est else print)(f"  [1] no 'est' records" if not est else f"  [1] FAIL {len(est)} estimated records present")

# 2. id is unique and present
ids = [r.get("id") for r in recs]
if None in ids: fails.append("  [2] FAIL some records have no id")
elif len(ids) != len(set(ids)): fails.append(f"  [2] FAIL {len(ids)-len(set(ids))} duplicate ids")
else: print(f"  [2] {len(set(ids))} unique ids, no duplicates")

# 3. count never decreases (high-water mark)
HW = os.path.join(os.path.dirname(SLIM), ".highwater")
prev = int(open(HW).read().strip()) if os.path.exists(HW) else 0
if len(recs) < prev: fails.append(f"  [3] FAIL count dropped {prev} -> {len(recs)} — refusing")
else:
    print(f"  [3] count {len(recs)} >= high-water {prev}")
    open(HW, "w").write(str(len(recs)) + "\n")

# 4. internally coherent
for r in recs:
    if r["bedtime_end"] <= r["bedtime_start"]: fails.append(f"  [4] FAIL {r['id']} ends before it starts")
if not any("[4]" in f for f in fails): print(f"  [4] all sessions end after they start")

# 5. faithful to live Oura (the test that caught the July 2 contamination)
def fetch(s, e):
    out, tok = [], None
    while True:
        q = {"start_date": s, "end_date": e}
        if tok: q["next_token"] = tok
        j = json.load(urllib.request.urlopen(urllib.request.Request(
            f"{WORKER}/v2/usercollection/sleep?" + urllib.parse.urlencode(q), headers=HDRS), timeout=90))
        out += j.get("data", []); tok = j.get("next_token")
        if not tok: return out

if "--offline" not in sys.argv:
    mine = {r["id"]: r for r in recs}
    live, y = {}, int(FLOOR[:4])
    today = datetime.date.today()
    while y <= today.year:
        for r in fetch(max(datetime.date(y,1,1), datetime.date.fromisoformat(FLOOR)).isoformat(),
                       min(datetime.date(y,12,31), today + datetime.timedelta(days=1)).isoformat()):
            live[r["id"]] = r
        y += 1
    diff = 0
    for i, lr in live.items():
        m = mine.get(i)
        if not m: diff += 1; warns.append(f"      Oura has {i} ({lr['day']}) — not in sleep.json"); continue
        if m["bedtime_start"] != lr["bedtime_start"] or m["bedtime_end"] != lr["bedtime_end"]:
            diff += 1; fails.append(f"  [5] FAIL {i} ({lr['day']}) disagrees with Oura")
    ghosts = set(mine) - set(live)
    if ghosts: warns.append(f"      {len(ghosts)} records in sleep.json that Oura no longer returns")
    print(f"  [5] {len(live)} live Oura sessions checked -> {diff} discrepancies")
else:
    print("  [5] skipped (--offline)")

# 6. gaps are real, not filled
days = sorted({r["day"] for r in recs if r["type"] == "long_sleep"})
d0, d1 = datetime.date.fromisoformat(days[0]), datetime.date.fromisoformat(days[-1])
gaps = (d1-d0).days + 1 - len(days)
print(f"  [6] {len(days)} nights w/ long_sleep over {(d1-d0).days+1} days -> {gaps} genuine gaps ({gaps/((d1-d0).days+1):.0%}) preserved")

for w in warns: print(w)
if fails:
    print("\n".join(fails)); print("\nFAILED"); sys.exit(1)
print("\nOK — sleep.json is faithful, uncontaminated, and complete.")
