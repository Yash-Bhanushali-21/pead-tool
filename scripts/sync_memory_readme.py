#!/usr/bin/env python3
"""
Copy the 'Current snapshot' section from PROJECT_MEMORY.md into README.md between
<!-- MEMORY_SNAPSHOT_START --> and <!-- MEMORY_SNAPSHOT_END -->.

Run after updating PROJECT_MEMORY.md (optional; agents may edit README block by hand instead).

Usage (repo root):
  python3 scripts/sync_memory_readme.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEM = ROOT / "PROJECT_MEMORY.md"
README = ROOT / "README.md"

START = "<!-- MEMORY_SNAPSHOT_START -->"
END = "<!-- MEMORY_SNAPSHOT_END -->"


def extract_snapshot(text: str) -> str:
    m = re.search(
        r"## Current snapshot\s*\n\n(.*?)(?=\n## [^#]|\Z)",
        text,
        re.DOTALL,
    )
    if not m:
        raise SystemExit("Could not find '## Current snapshot' in PROJECT_MEMORY.md")
    body = m.group(1).strip()
    lines = [ln.rstrip() for ln in body.splitlines()]
    quoted: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s or s == "---":
            continue
        if s.startswith(">"):
            quoted.append(s)
        else:
            quoted.append(f"> {s}")
    intro = (
        "> **Living context:** Read all **`memory-bank/*.md`** at task start (Cursor rule `memory-bank.mdc`). "
        "Dated **change log** and README snapshot source: [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md)."
    )
    inner = intro + "\n" + "\n".join(quoted)
    return f"{START}\n\n{inner}\n\n{END}"


def main() -> None:
    snap = extract_snapshot(MEM.read_text(encoding="utf-8"))
    readme = README.read_text(encoding="utf-8")
    if START not in readme or END not in readme:
        raise SystemExit("README.md missing memory markers; add them first.")
    pattern = re.compile(
        re.escape(START) + r".*?" + re.escape(END),
        re.DOTALL,
    )
    new_readme, n = pattern.subn(snap, readme, count=1)
    if n != 1:
        raise SystemExit("Failed to replace exactly one memory block in README.md")
    README.write_text(new_readme, encoding="utf-8")
    print("Updated README.md memory block from PROJECT_MEMORY.md")


if __name__ == "__main__":
    main()
