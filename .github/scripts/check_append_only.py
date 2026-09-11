#!/usr/bin/env python3
"""Refuse any change that overwrites or removes data that is already committed.

Rikki, 2026-09-10: "ensure that data is only being added, not overwriting or
removing old data." This compares the working tree against a committed base
(default HEAD) and exits 1 if anything already committed would be lost:

  · *.jsonl under data/        committed bytes must be an exact prefix of the new file
  · data/sleep.json            every committed record (by id) still present and unchanged
  · data/sleep_revisions.json  committed entries stay first and unchanged
  · frozen files               data/sleep_2021_csv.jsonl and everything under exports/
                               stay byte-identical
  · no committed data file may disappear

New files and appended records always pass. Dotfiles (.highwater) and *.md are exempt.
Any git error fails closed.

    python3 .github/scripts/check_append_only.py             # working tree vs HEAD
    python3 .github/scripts/check_append_only.py --base REF  # working tree vs REF
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FROZEN_FILES = {"data/sleep_2021_csv.jsonl"}
FROZEN_DIRS = ("exports/",)
KEYED_JSON = {"data/sleep.json": "id"}
LIST_JSON = {"data/sleep_revisions.json"}


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, check=True).stdout


def exempt(path):
    name = os.path.basename(path)
    return name.startswith(".") or name.endswith(".md")


def main():
    base = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "HEAD"
    tracked = git("ls-tree", "-r", "--name-only", base, "--", "data", "exports").decode().splitlines()
    fails, checked = [], 0
    for path in tracked:
        if exempt(path):
            continue
        old = git("show", f"{base}:{path}")
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            fails.append(f"REMOVED   {path} (committed in {base}, missing now)")
            continue
        with open(full, "rb") as f:
            new = f.read()
        checked += 1
        if path in FROZEN_FILES or path.startswith(FROZEN_DIRS):
            if new != old:
                fails.append(f"CHANGED   {path} is frozen and must stay byte-identical")
        elif path in KEYED_JSON:
            key = KEYED_JSON[path]
            o = {r[key]: r for r in json.loads(old)}
            n = {r[key]: r for r in json.loads(new)}
            gone = [k for k in o if k not in n]
            diff = [k for k in o if k in n and o[k] != n[k]]
            if gone:
                fails.append(f"REMOVED   {len(gone)} record(s) from {path}, e.g. {gone[:3]}")
            if diff:
                fails.append(f"OVERWROTE {len(diff)} record(s) in {path}, e.g. {diff[:3]}")
        elif path in LIST_JSON:
            o, n = json.loads(old), json.loads(new)
            if n[:len(o)] != o:
                fails.append(f"REWROTE   {path}: committed entries must stay first and unchanged")
        elif path.endswith(".jsonl"):
            if not new.startswith(old):
                ol, nl = old.splitlines(), new.splitlines()
                i = next((i for i, (a, b) in enumerate(zip(ol, nl)) if a != b), min(len(ol), len(nl)))
                fails.append(f"REWROTE   {path}: committed content is no longer an exact prefix "
                             f"(first difference at line {i + 1})")
        elif new != old:
            fails.append(f"CHANGED   {path}: not an append-only format, so it must stay byte-identical")

    if fails:
        print("APPEND-ONLY CHECK FAILED — nothing may be committed:")
        for line in fails:
            print("  " + line)
        sys.exit(1)
    print(f"append-only OK: {checked} committed data files intact vs {base}; only additions")


if __name__ == "__main__":
    main()
