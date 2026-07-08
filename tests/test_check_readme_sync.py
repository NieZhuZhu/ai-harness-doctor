import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "scripts"))
import check_readme_sync as sync  # noqa: E402


REFERENCE = """# Title

Intro with a [link](https://example.com).

```bash
npm test   # run tests
```

## Section

| A | B |
|---|---|
| 1 | 2 |

```json
{ "k": 1 }
```
"""


class ExtractTests(unittest.TestCase):
    def test_headings_ignore_fenced_hash_lines(self):
        headings = sync.extract_headings(REFERENCE)
        self.assertEqual(headings, [(1, "Title"), (2, "Section")])

    def test_code_blocks_keep_body_verbatim(self):
        blocks = sync.extract_code_blocks(REFERENCE)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0], "npm test   # run tests")
        self.assertEqual(blocks[1], '{ "k": 1 }')

    def test_table_rows_and_links_skip_fences(self):
        # The fenced ``# run tests`` comment must not count as anything, and the
        # table has three pipe rows (header, separator, one data row).
        self.assertEqual(sync.count_table_rows(REFERENCE), 3)
        self.assertEqual(sync.count_links(REFERENCE), 1)


class CompareTests(unittest.TestCase):
    def test_identical_structure_has_no_problems(self):
        # Prose differs, structure identical → in sync.
        translated = REFERENCE.replace("Intro with a", "别のイントロ")
        problems = sync.compare("README.md", REFERENCE, "README.ja.md", translated)
        self.assertEqual(problems, [])

    def test_heading_count_mismatch(self):
        extra = REFERENCE + "\n## Extra\n"
        problems = sync.compare("README.md", REFERENCE, "README.zh-CN.md", extra)
        self.assertTrue(any("headings" in p for p in problems))

    def test_code_block_content_mismatch(self):
        # Translating an inline code comment must be caught.
        drifted = REFERENCE.replace("# run tests", "# 运行测试")
        problems = sync.compare("README.md", REFERENCE, "README.zh-CN.md", drifted)
        self.assertTrue(any("code block" in p for p in problems))

    def test_code_block_count_mismatch(self):
        dropped = REFERENCE.replace('```json\n{ "k": 1 }\n```\n', "")
        problems = sync.compare("README.md", REFERENCE, "README.ja.md", dropped)
        self.assertTrue(any("code blocks" in p for p in problems))

    def test_table_row_mismatch(self):
        extra_row = REFERENCE.replace("| 1 | 2 |", "| 1 | 2 |\n| 3 | 4 |")
        problems = sync.compare("README.md", REFERENCE, "README.zh-CN.md", extra_row)
        self.assertTrue(any("table rows" in p for p in problems))

    def test_link_count_mismatch(self):
        dropped_link = REFERENCE.replace("[link](https://example.com)", "link")
        problems = sync.compare("README.md", REFERENCE, "README.ja.md", dropped_link)
        self.assertTrue(any("links" in p for p in problems))


class RepoReadmesTests(unittest.TestCase):
    def test_shipped_readmes_are_in_sync(self):
        reference_text = (ROOT / sync.README_FILES[0]).read_text(encoding="utf-8")
        for name in sync.README_FILES[1:]:
            path = ROOT / name
            if not path.exists():
                continue
            problems = sync.compare(
                sync.README_FILES[0], reference_text, name, path.read_text(encoding="utf-8")
            )
            self.assertEqual(problems, [], f"{name} diverged: {problems}")


if __name__ == "__main__":
    unittest.main()
