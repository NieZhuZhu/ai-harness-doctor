import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import facts  # noqa: E402


def _can_symlink_files():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        target = root / "target"
        link = root / "link"
        target.write_text("target\n", encoding="utf-8")
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            return False
        return link.is_symlink()


class IterCodeTokensTests(unittest.TestCase):
    def test_yields_fenced_commands_and_inline_spans(self):
        text = "Run `npm test` first.\n```bash\nnpm run build\n```\n"
        tokens = [tok for _lineno, tok in facts.iter_code_tokens(text)]
        self.assertIn("npm test", tokens)
        self.assertIn("npm run build", tokens)

    def test_skips_shell_comment_lines_inside_fence(self):
        text = "```bash\n# make sure the tests pass\nnpm run build\n```\n"
        tokens = [tok for _lineno, tok in facts.iter_code_tokens(text)]
        self.assertEqual(tokens, ["npm run build"])

    def test_backticks_inside_fenced_comment_do_not_leak_tokens(self):
        # A shell comment inside a fence is skipped by the CORR-02 guard; the
        # inline-backtick regex must not leak substrings out of it.
        text = (
            "```bash\n"
            "# see `config.yaml` for details\n"
            "npm run build\n"
            "```\n"
        )
        tokens = [tok for _lineno, tok in facts.iter_code_tokens(text)]
        self.assertNotIn("config.yaml", tokens)
        self.assertEqual(tokens, ["npm run build"])

    def test_command_substitution_backticks_not_split_into_extra_tokens(self):
        # Literal backticks inside a fenced command line are command
        # substitution, not Markdown inline spans; the whole line is the token.
        text = "```bash\nRELEASE=`date +%s` npm publish\n```\n"
        tokens = [tok for _lineno, tok in facts.iter_code_tokens(text)]
        self.assertEqual(tokens, ["RELEASE=`date +%s` npm publish"])

    def test_inline_spans_still_scanned_outside_fences(self):
        text = "Prefer `pnpm install` over `npm install`.\n"
        tokens = [tok for _lineno, tok in facts.iter_code_tokens(text)]
        self.assertEqual(tokens, ["pnpm install", "npm install"])

    def test_html_comment_backtick_spans_are_masked(self):
        # A ``<!-- `npm` -->`` note is hidden Markdown commentary, not a
        # command declaration; ``iter_code_tokens`` must not leak backtick
        # spans out of it or ``declared_package_managers`` picks up phantom
        # legacy managers (round 50, same false-positive class as fenced-#).
        text = "Prefer `pnpm install`. <!-- previously we ran `npm install` -->\n"
        tokens = [tok for _lineno, tok in facts.iter_code_tokens(text)]
        self.assertEqual(tokens, ["pnpm install"])

    def test_multiline_html_comment_masks_across_lines(self):
        text = (
            "Prefer `pnpm`.\n"
            "<!--\n"
            "Older setup used `npm` and `yarn`.\n"
            "-->\n"
            "Run `pnpm test`.\n"
        )
        tokens = [tok for _lineno, tok in facts.iter_code_tokens(text)]
        # Legacy tokens inside the multi-line comment are dropped; real
        # backtick spans outside it survive with their original line numbers.
        self.assertEqual(tokens, ["pnpm", "pnpm test"])


class MaskHtmlCommentsTests(unittest.TestCase):
    def test_single_line_comment_preserves_surrounding_text(self):
        masked = facts.mask_html_comments("keep <!-- drop this --> tail")
        self.assertEqual(len(masked), len("keep <!-- drop this --> tail"))
        self.assertTrue(masked.startswith("keep "))
        self.assertTrue(masked.endswith(" tail"))
        self.assertNotIn("drop", masked)

    def test_multiline_comment_preserves_newlines(self):
        original = "a\n<!--\nlegacy\ncontent\n-->\nb\n"
        masked = facts.mask_html_comments(original)
        # Line count must match so downstream line numbers stay stable.
        self.assertEqual(masked.count("\n"), original.count("\n"))
        self.assertNotIn("legacy", masked)
        self.assertNotIn("content", masked)
        self.assertTrue(masked.startswith("a\n"))
        self.assertTrue(masked.endswith("\nb\n"))

    def test_unterminated_comment_masks_to_end(self):
        # A missing ``-->`` still masks everything after the opener so a
        # dangling comment cannot leak a legacy tool mention.
        masked = facts.mask_html_comments("ok <!-- yarn npm\nmore npm")
        self.assertNotIn("yarn", masked)
        self.assertNotIn("more npm", masked)


@unittest.skipUnless(_can_symlink_files(), "file symlinks unsupported on this platform")
class IsCanonicalAgentsPointerSymlinkTests(unittest.TestCase):
    def test_sibling_symlink_to_agents_md_is_canonical(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td).resolve()
            (repo / "AGENTS.md").write_text("# canonical\n", encoding="utf-8")
            (repo / "CLAUDE.md").symlink_to("AGENTS.md")
            self.assertTrue(
                facts.is_canonical_agents_pointer_symlink(repo, repo / "CLAUDE.md")
            )

    def test_nested_sibling_symlink_to_agents_md_is_canonical(self):
        # pydantic-ai puts one at the root AND inside `tests/`; both are safe.
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td).resolve()
            (repo / "tests").mkdir()
            (repo / "tests" / "AGENTS.md").write_text("# tests\n", encoding="utf-8")
            (repo / "tests" / "CLAUDE.md").symlink_to("AGENTS.md")
            self.assertTrue(
                facts.is_canonical_agents_pointer_symlink(
                    repo, repo / "tests" / "CLAUDE.md"
                )
            )

    def test_regular_file_pointer_is_not_a_canonical_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td).resolve()
            (repo / "AGENTS.md").write_text("# canonical\n", encoding="utf-8")
            (repo / "CLAUDE.md").write_text(
                "Canonical instructions live in AGENTS.md.\n", encoding="utf-8"
            )
            self.assertFalse(
                facts.is_canonical_agents_pointer_symlink(repo, repo / "CLAUDE.md")
            )

    def test_symlink_to_non_agents_target_is_not_canonical(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td).resolve()
            (repo / "AGENTS.md").write_text("# canonical\n", encoding="utf-8")
            (repo / "docs.md").write_text("# docs\n", encoding="utf-8")
            (repo / "CLAUDE.md").symlink_to("docs.md")
            self.assertFalse(
                facts.is_canonical_agents_pointer_symlink(repo, repo / "CLAUDE.md")
            )

    def test_cross_directory_symlink_is_not_canonical(self):
        # A cross-subtree symlink stops being trivially drift-proof at the
        # canonical-pointer level (the sibling invariant is what makes the
        # pattern safe), so we deliberately do not classify it as canonical.
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td).resolve()
            (repo / "AGENTS.md").write_text("# canonical\n", encoding="utf-8")
            (repo / "docs").mkdir()
            (repo / "docs" / "CLAUDE.md").symlink_to("../AGENTS.md")
            self.assertFalse(
                facts.is_canonical_agents_pointer_symlink(
                    repo, repo / "docs" / "CLAUDE.md"
                )
            )

    def test_broken_symlink_is_not_canonical(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td).resolve()
            (repo / "CLAUDE.md").symlink_to("AGENTS.md")  # target missing
            self.assertFalse(
                facts.is_canonical_agents_pointer_symlink(repo, repo / "CLAUDE.md")
            )

    def test_symlink_escaping_root_is_not_canonical(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td).resolve()
            outside = base / "outside" / "AGENTS.md"
            outside.parent.mkdir()
            outside.write_text("# elsewhere\n", encoding="utf-8")
            repo = base / "repo"
            repo.mkdir()
            (repo / "CLAUDE.md").symlink_to(outside)
            self.assertFalse(
                facts.is_canonical_agents_pointer_symlink(repo, repo / "CLAUDE.md")
            )


if __name__ == "__main__":
    unittest.main()
