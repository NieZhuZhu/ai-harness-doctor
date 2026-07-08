#!/usr/bin/env python3
"""Check that the trilingual READMEs stay structurally in sync.

Dev/CI-only helper (Python standard library only). The English, Simplified
Chinese, and Japanese READMEs are expected to differ in prose but keep an
identical structural skeleton:

  1. Headings: same count, order, and levels.
  2. Fenced code blocks: same count and byte-identical content, in order.
     Commands and JSON examples (including their inline ``#`` comments) must
     not diverge between translations.
  3. Table rows: same count (translated prose lives inside cells, but the
     table shape must match).
  4. Links: same count (link targets are not translated).

This guards against a translation drifting out of sync when a section, command,
table row, or link is added, removed, or re-nested in only one file.

Exit codes:
  0  all READMEs share the same structure (or a file is missing and the check
     degrades to advisory).
  1  the structure diverges between READMEs.
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
# Markdown inline links and images: [text](target) / ![alt](target).
LINK_RE = re.compile(r"!?\[[^\]]*\]\([^)]+\)")


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


def extract_code_blocks(text):
    """Return a list of fenced code-block bodies, in document order.

    The body excludes the opening and closing fence lines. Content is kept
    verbatim so that commands, JSON, and inline ``#`` comments must match
    byte-for-byte across translations.
    """
    blocks = []
    current = None
    for line in text.splitlines():
        if FENCE_RE.match(line):
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
            continue
        if current is not None:
            current.append(line)
    # An unterminated fence still yields its captured body, mirroring how the
    # heading/link extractors treat the trailing region.
    if current is not None:
        blocks.append("\n".join(current))
    return blocks


def count_table_rows(text):
    """Count Markdown table rows (lines starting with '|'), skipping fences."""
    count = 0
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.lstrip().startswith("|"):
            count += 1
    return count


def count_links(text):
    """Count Markdown inline links/images outside fenced code blocks."""
    count = 0
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        count += len(LINK_RE.findall(line))
    return count


def compare(reference_name, reference_text, name, text):
    """Return a list of human-readable mismatch strings (empty when in sync)."""
    problems = []

    ref_headings = extract_headings(reference_text)
    headings = extract_headings(text)
    ref_levels = [level for level, _ in ref_headings]
    levels = [level for level, _ in headings]
    if len(levels) != len(ref_levels):
        problems.append(
            f"{name} has {len(levels)} headings but {reference_name} has {len(ref_levels)}"
        )
    for index in range(min(len(levels), len(ref_levels))):
        if levels[index] != ref_levels[index]:
            ref_level, ref_title = ref_headings[index]
            cur_level, cur_title = headings[index]
            problems.append(
                f"heading #{index + 1}: {reference_name} has level {ref_level} "
                f"({ref_title!r}) but {name} has level {cur_level} ({cur_title!r})"
            )
            break

    ref_blocks = extract_code_blocks(reference_text)
    blocks = extract_code_blocks(text)
    if len(blocks) != len(ref_blocks):
        problems.append(
            f"{name} has {len(blocks)} code blocks but {reference_name} has {len(ref_blocks)}"
        )
    for index in range(min(len(blocks), len(ref_blocks))):
        if blocks[index] != ref_blocks[index]:
            problems.append(
                f"code block #{index + 1} differs from {reference_name} "
                f"(fenced code, including inline comments, must be identical)"
            )
            break

    ref_rows = count_table_rows(reference_text)
    rows = count_table_rows(text)
    if rows != ref_rows:
        problems.append(
            f"{name} has {rows} table rows but {reference_name} has {ref_rows}"
        )

    ref_links = count_links(reference_text)
    links = count_links(text)
    if links != ref_links:
        problems.append(
            f"{name} has {links} links but {reference_name} has {ref_links}"
        )

    return problems


def main():
    reference_name = README_FILES[0]
    reference_path = ROOT / reference_name

    if not reference_path.exists():
        print(f"[readme-sync] advisory: reference {reference_name} not found; skipping check")
        return 0

    reference_text = reference_path.read_text(encoding="utf-8")

    diverged = False
    for name in README_FILES[1:]:
        path = ROOT / name
        if not path.exists():
            print(f"[readme-sync] advisory: {name} not found; skipping comparison")
            continue

        problems = compare(reference_name, reference_text, name, path.read_text(encoding="utf-8"))
        for problem in problems:
            diverged = True
            print(f"[readme-sync] MISMATCH: {problem}")

    if diverged:
        print("[readme-sync] FAIL: README structures diverge; keep translations in sync.")
        return 1

    print(
        f"[readme-sync] OK: {len(extract_headings(reference_text))} headings, "
        f"{len(extract_code_blocks(reference_text))} code blocks, "
        f"{count_table_rows(reference_text)} table rows, {count_links(reference_text)} links "
        f"aligned across {len(README_FILES)} READMEs."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
