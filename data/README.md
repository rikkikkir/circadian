# data/sleep.json — the source of truth

Every session Oura recorded for Rikki since the ring began: **2021-01-12 onward**.
Measured only. **No estimated, projected, or modelled records — ever.**
Projections belong to render time; they are never written back here.

## Shape

One object per sleep session, Oura-native field names:

| field | meaning |
|---|---|
| `id` | Oura session UUID — **the merge key** |
| `day` | the day Oura files the session under (a night lands under the *next* day) |
| `bedtime_start` / `bedtime_end` | ISO 8601 **with the real UTC offset preserved** |
| `off` | that offset in minutes (−300/−240 Michigan · −360/−420 Montana) |
| `dur` | hours in bed |
| `tsd` `rem` `deep` `light` | sleep durations, seconds |
| `hrv` `hr` | nightly averages |
| `score` | always `null` for `src: "api"` records — Oura's sleep-session data has no score field |
| `type` | `long_sleep` = a real night · `sleep` = a nap |
| `src` | **provenance.** `api` = pulled live from Oura · `csv` = recovered from an export |

`sleep_revisions.json` holds later versions of nights that are already here (see Rules).

## Two provenances, and why

The Oura API returns **zero sessions before 2022-01-24**. It is not that the ring
started then — it is as far back as the API reaches. 304 nights from
**2021-01-12 → 2022-01-19** survive only inside one 54-column CSV export
(`~/Documents/Documents(1)/oura_2021-01-01_2023-02-01_trends.csv`). Those carry
`src: "csv"`, a synthetic `csv-<date>-<time>` id, and no naps — a trends export is
daily-resolution, one row per night.

They were checked before merging: of 283 nights where the CSV and the API overlap,
**282 matched to the second**. The one that didn't is the most instructive record here —
2022-04-02, which the CSV holds as a single 09:48→18:04 sleep and the API now returns
as six fragments. **Oura re-scores nights after the fact.** That is exactly why the
merge key is `id` and not `day` or `bedtime_start`.

`verify.py` diffs `src: "api"` records against live Oura and skips `src: "csv"` ones —
there is nothing live left to diff them against.

## Rules

- **Merge on `id`.** Not `day` — 126 days in 2025 alone have more than one session.
  Not `bedtime_start` — Oura re-scores nights afterward and that moves the timestamp,
  so a correction keyed that way would land *beside* the stale row.
- **Append-only.** Records are only ever added. A record already in `sleep.json` is never
  changed or removed. When Oura re-scores a night, its new version is appended to
  `sleep_revisions.json` as `{captured_at, id, kind: "revision", record}`; a night's current
  version is its last revision, else its record here. `kind: "recovered"` entries are
  earlier versions restored from git history — history only.
  `.github/scripts/check_append_only.py` refuses any commit that would change or remove a
  committed record. (Adopted 2026-09-10; the one earlier in-place correction, 2026-08-25,
  was recovered into `sleep_revisions.json`.)
- **Gaps are real.** 312 nights (19%) have no record — the ring was off, or the night
  was lived without it. Longest: 2025-03-27 → 2025-04-21 (24 nights). Jun 30–Jul 1 2026
  is the move to Bozeman. **Never interpolate a gap. Render it as a gap.**
- **`off` is stored because it is true.** Anything that draws a wall-clock time must
  either honour it or state plainly which fixed frame it chose instead.
- **Data flows Code → Design, never Design → Code.** Claude Design will invent records
  to finish a picture — fabricated "12.0h" nights in a July 2026 export rendered
  identically to measured ones. Designed pages must fetch this file and inline zero records.

## Verify

    python3 verify.py            # diffs each night's current version against live Oura
    python3 verify.py --offline  # structure only, no network

Green means faithful. That is the whole point of this file: *finding out when it's wrong.*

## Provenance

Captured 2026-07-16 · **2,811 sessions · 2021-01-12 → 2026-07-16** ·
2,507 from the API + 304 recovered from CSV · 1,627 nights + 1,126 naps ·
385 genuine gaps (19%) preserved as gaps · 0 discrepancies vs live Oura.
Append-only since 2026-09-10.
