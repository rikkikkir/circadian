# data/sleep.json — the source of truth

Every session Oura recorded for Rikki since the ring began: 2022-01-24 onward.
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
| `hrv` `hr` `score` | nightly averages |
| `type` | `long_sleep` = a real night · `sleep` = a nap |

## Rules

- **Merge on `id`.** Not `day` — 126 days in 2025 alone have more than one session.
  Not `bedtime_start` — Oura re-scores nights afterward and that moves the timestamp,
  so a correction would land *beside* the stale row instead of replacing it.
- **Append-only.** Records are added or corrected, never deleted.
- **Gaps are real.** 312 nights (19%) have no record — the ring was off, or the night
  was lived without it. Longest: 2025-03-27 → 2025-04-21 (24 nights). Jun 30–Jul 1 2026
  is the move to Bozeman. **Never interpolate a gap. Render it as a gap.**
- **`off` is stored because it is true.** Anything that draws a wall-clock time must
  either honour it or state plainly which fixed frame it chose instead.
- **Data flows Code → Design, never Design → Code.** Claude Design will invent records
  to finish a picture — four fabricated "12.0h" nights in a July 2026 export rendered
  identically to measured ones. Designed pages must fetch this file and inline zero records.

## Verify

    python3 verify.py            # diffs every record against live Oura
    python3 verify.py --offline  # structure only, no network

Green means faithful. That is the whole point of this file: *finding out when it's wrong.*

## Provenance

Captured 2026-07-16 · 2,507 sessions · 1,381 nights + 1,126 naps · 0 discrepancies vs Oura.
