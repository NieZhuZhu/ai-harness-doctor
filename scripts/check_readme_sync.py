#!/usr/bin/env python3
"""Check that the trilingual READMEs share the same heading structure.

Dev/CI-only helper (Python standard library only). The English, Simplified
Chinese, and Japanese READMEs are expected to differ in prose but keep an
identical heading skeleton (same number of headings, in the same order, at the
same levels). This guards against a translation drifting out of sync when a
section is added, removed, or re-nested in only one file.

Exit codes:
  0  all READMEs share the same heading structure (or a file is missing and the
     check degrades to advisory).
  1  the heading structure diverges between READMEs.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The canonical/reference file is listed first; every other file is compared
# against it.
README_FILES = [
    "README.md",
    "README.zh-CN.md",
    "README.ja.md",
]

# Matches ATX headings (# ... through ###### ...). A fenced code block can
# contain lines that start with '#', so we skip content inside ``` fences.
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def extract_headings(text):
    """Return a list of (level, title) tuples, ignoring fenced code blocks."""
    headings = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            headings.append((len(match.group(1)), match.group(2).strip()))
    return headings


def main():
    reference_name = README_FILES[0]
    reference_path = ROOT / reference_name

    if not reference_path.exists():
        print(f"[readme-sync] advisory: reference {reference_name} not found; skipping check")
        return 0

    reference = extract_headings(reference_path.read_text(encoding="utf-8"))
    reference_levels = [level for level, _ in reference]

    diverged = False
    for name in README_FILES[1:]:
        path = ROOT / name
        if not path.exists():
            print(f"[readme-sync] advisory: {name} not found; skipping comparison")
            continue

        headings = extract_headings(path.read_text(encoding="utf-8"))
        levels = [level for level, _ in headings]

        if len(levels) != len(reference_levels):
            diverged = True
            print(
                f"[readme-sync] MISMATCH: {name} has {len(levels)} headings "
                f"but {reference_name} has {len(reference_levels)}"
            )

        for index in range(min(len(levels), len(reference_levels))):
            if levels[index] != reference_levels[index]:
                diverged = True
                ref_level, ref_title = reference[index]
                cur_level, cur_title = headings[index]
                print(
                    f"[readme-sync] MISMATCH at heading #{index + 1}: "
                    f"{reference_name} has level {ref_level} ({ref_title!r}) but "
                    f"{name} has level {cur_level} ({cur_title!r})"
                )
                break

    if diverged:
        print("[readme-sync] FAIL: README heading structures diverge; keep translations in sync.")
        return 1

    print(f"[readme-sync] OK: {len(reference_levels)} headings aligned across {len(README_FILES)} READMEs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
